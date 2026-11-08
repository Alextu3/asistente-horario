"""Horario semanal acordado con Alberto (v2). /cargar_horario lo crea en el calendario Asistente."""
from datetime import date, datetime, timedelta

import calendario
from config import TZ

DIAS = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]

# (día 0=lunes, inicio, fin, título)
BLOQUES = [
    (0, "06:30", "07:15", "📖 Árabe (repaso)"),
    (0, "14:10", "14:25", "🚶 Paseo corto"),
    (0, "20:00", "21:00", "🧩 Autismo"),
    (1, "06:30", "07:00", "📖 Árabe (repaso)"),
    (1, "14:45", "15:15", "🚶 Paseo"),
    (1, "15:30", "17:00", "🧩 Autismo: ImPACT"),
    (2, "14:45", "15:15", "🚶 Paseo"),
    (2, "15:30", "16:30", "📖 Árabe"),
    (2, "16:30", "17:30", "🧩 Autismo: DENVER"),
    (2, "18:00", "19:00", "🏃 Deporte"),
    (3, "06:30", "07:00", "📖 Árabe (repaso)"),
    (3, "14:45", "15:15", "🚶 Paseo"),
    (3, "15:30", "17:00", "🧩 Autismo: JASPER"),
    (4, "14:40", "15:10", "🚶 Paseo"),
    (4, "15:10", "16:10", "📖 Árabe"),
    (4, "16:10", "17:10", "🧩 Autismo: PEERS"),
    (5, "10:00", "12:00", "🧩 Autismo (proyecto más atrasado)"),
    (5, "17:00", "18:00", "📖 Árabe"),
    (6, "09:15", "10:30", "📖 Árabe"),
    (6, "19:00", "19:15", "🗓️ Planificar la semana con el bot"),
]


def _proximo(dia_semana: int, desde: date) -> date:
    return desde + timedelta(days=(dia_semana - desde.weekday()) % 7)


def cargar():
    hoy = datetime.now(TZ).date()
    creados = 0
    for dia, ini, fin, titulo in BLOQUES:
        d = _proximo(dia, hoy + timedelta(days=1))
        h1, m1 = map(int, ini.split(":"))
        h2, m2 = map(int, fin.split(":"))
        calendario.crear_evento(
            titulo,
            datetime(d.year, d.month, d.day, h1, m1, tzinfo=TZ),
            datetime(d.year, d.month, d.day, h2, m2, tzinfo=TZ),
            avisos_min=[5],
            rrule=f"FREQ=WEEKLY;BYDAY={DIAS[dia]}",
        )
        creados += 1
    return creados
