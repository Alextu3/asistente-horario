"""Acceso al Calendario de Apple (iCloud) por CalDAV."""
import uuid
from datetime import date, datetime, timedelta

import caldav
from icalendar import Alarm, Calendar, Event

from config import CALENDARIO_BOT, ICLOUD_APP_PASSWORD, ICLOUD_USER, TZ

_cliente = None


def _calendarios():
    global _cliente
    if _cliente is None:
        _cliente = caldav.DAVClient(
            url="https://caldav.icloud.com",
            username=ICLOUD_USER,
            password=ICLOUD_APP_PASSWORD,
        )
    return _cliente.principal().calendars()


def _calendario_bot():
    for cal in _calendarios():
        if (cal.name or "").strip().lower() == CALENDARIO_BOT.lower():
            return cal
    raise RuntimeError(
        f"No encuentro el calendario '{CALENDARIO_BOT}' en iCloud. Créalo en la app Calendario."
    )


def _a_local(valor):
    if isinstance(valor, datetime):
        if valor.tzinfo is None:
            return valor.replace(tzinfo=TZ)
        return valor.astimezone(TZ)
    if isinstance(valor, date):  # evento de día completo
        return datetime(valor.year, valor.month, valor.day, tzinfo=TZ)
    return valor


def eventos(desde: datetime, hasta: datetime):
    """Lista de eventos de todos los calendarios, ordenados por inicio."""
    resultado = []
    for cal in _calendarios():
        try:
            encontrados = cal.search(start=desde, end=hasta, event=True, expand=True)
        except Exception:  # calendarios de solo lectura o sin eventos (p. ej. festivos)
            continue
        for ev in encontrados:
            for comp in ev.icalendar_instance.walk("VEVENT"):
                inicio = comp.get("DTSTART").dt
                fin = comp.get("DTEND").dt if comp.get("DTEND") else inicio
                resultado.append(
                    {
                        "uid": str(comp.get("UID")),
                        "titulo": str(comp.get("SUMMARY", "")),
                        "inicio": _a_local(inicio),
                        "fin": _a_local(fin),
                        "todo_el_dia": not isinstance(inicio, datetime),
                        "lugar": str(comp.get("LOCATION", "") or ""),
                        "notas": str(comp.get("DESCRIPTION", "") or ""),
                        "calendario": cal.name,
                    }
                )
    resultado.sort(key=lambda e: e["inicio"])
    return resultado


def crear_evento(titulo, inicio: datetime, fin: datetime, avisos_min=(10,), notas="", lugar="", rrule=None):
    cal_ics = Calendar()
    cal_ics.add("prodid", "-//asistente-horario//ES")
    cal_ics.add("version", "2.0")
    ev = Event()
    uid = f"{uuid.uuid4()}@asistente-horario"
    ev.add("uid", uid)
    ev.add("summary", titulo)
    ev.add("dtstart", inicio)
    ev.add("dtend", fin)
    ev.add("dtstamp", datetime.now(TZ))
    if notas:
        ev.add("description", notas)
    if lugar:
        ev.add("location", lugar)
    if rrule:
        ev.add("rrule", _parse_rrule(rrule))
    for m in avisos_min or []:
        a = Alarm()
        a.add("action", "DISPLAY")
        a.add("description", titulo)
        a.add("trigger", timedelta(minutes=-int(m)))
        ev.add_component(a)
    cal_ics.add_component(ev)
    cal_ics.add_missing_timezones()
    _calendario_bot().save_event(cal_ics.to_ical().decode())
    return uid


def borrar_evento(uid: str):
    _calendario_bot().event_by_uid(uid).delete()


def _parse_rrule(texto: str):
    """'FREQ=WEEKLY;BYDAY=TU,TH' -> dict para icalendar."""
    regla = {}
    for parte in texto.split(";"):
        if "=" in parte:
            k, v = parte.split("=", 1)
            regla[k.strip().upper()] = v.split(",") if "," in v else v
    return regla


def huecos_libres(desde: datetime, hasta: datetime, duracion_min: int, franjas=None, max_resultados=10):
    """Huecos libres de al menos `duracion_min`.

    franjas: lista de {"dias": [0..6], "inicio": "HH:MM", "fin": "HH:MM"} donde se permite buscar.
    Por defecto, todos los días de 08:00 a 21:30.
    """
    franjas = franjas or [{"dias": list(range(7)), "inicio": "08:00", "fin": "21:30"}]
    ocupados = [(e["inicio"], e["fin"]) for e in eventos(desde, hasta) if not e["todo_el_dia"]]
    dur = timedelta(minutes=duracion_min)
    resultado = []
    dia = desde.date()
    while dia <= hasta.date() and len(resultado) < max_resultados:
        for f in franjas:
            if dia.weekday() not in f["dias"]:
                continue
            h1, m1 = map(int, f["inicio"].split(":"))
            h2, m2 = map(int, f["fin"].split(":"))
            ini = max(datetime(dia.year, dia.month, dia.day, h1, m1, tzinfo=TZ), desde)
            fin = min(datetime(dia.year, dia.month, dia.day, h2, m2, tzinfo=TZ), hasta)
            cursor = ini
            for o_ini, o_fin in sorted(ocupados):
                if o_fin <= cursor or o_ini >= fin:
                    continue
                if o_ini - cursor >= dur:
                    resultado.append((cursor, o_ini))
                cursor = max(cursor, o_fin)
            if fin - cursor >= dur:
                resultado.append((cursor, fin))
        dia += timedelta(days=1)
    resultado.sort()
    return resultado[:max_resultados]
