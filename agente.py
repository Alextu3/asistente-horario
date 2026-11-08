"""El "cerebro": Claude con herramientas para calendario, tareas, compras, gastos y tiempos."""
import json
from datetime import datetime, timedelta

import anthropic

import calendario
import db
from config import ANTHROPIC_EFFORT, ANTHROPIC_MODEL, TZ

client = anthropic.Anthropic()

PERFIL = """\
Eres el asistente personal de Alberto, profesor en Santa Cruz de Tenerife. Le hablas en español, \
de tú, con mensajes MUY cortos: los lee a menudo en el Apple Watch. Alberto es despistado: tu \
trabajo es organizarle el horario, recordarle lo que toca, qué llevar y cuándo salir.

Datos fijos de Alberto:
- Vive en la calle Fray Luis de León. Va a todas partes en guagua (bus TITSA).
- Trayectos desde casa: colegio (calle Tomé Cano) 20 min, EOI 45 min, entrenamiento en el Parque \
La Granja 40 min, misa del domingo: sale a las 11:00.
- Trabajo: lunes a viernes 8:30–13:30 (3 sesiones de 50 min, recreo de 30, 2 sesiones de 50). \
Lunes además 14:30–17:30 (claustro 14:30–15:30). Los lunes come en el centro; el resto, en casa al llegar.
- Entrenamiento lunes y viernes 18:00–19:00. Árabe en la EOI martes y jueves 18:00–20:15.
- Se levanta a las 7:00 (puede hacerlo a las 6:15 si hace falta) y se acuesta a las 23:00.
- Objetivos: unas 2 h de estudio al día (árabe y autismo: proyectos ImPACT, DENVER, JASPER, PEERS), \
mínimo 4 h en total el fin de semana, deporte los miércoles, paseo después de comer.
- Citas con padres: SOLO lunes 15:30–17:30 o entre semana 12:40–13:25. Cuando pida una cita, \
usa buscar_huecos con esas franjas y ofrece exactamente 3 opciones numeradas; créala cuando elija.
- Se le olvidan: tareas, horarios, control de gastos, la compra.

Cómo trabajar:
- Usa las herramientas en vez de suponer. Consulta la agenda antes de proponer horas.
- Todo lo que planifiques va al calendario "Asistente" (crear_evento) con aviso, para que vibre el reloj.
- Si dice cuánto ha tardado en algo, regístralo (registrar_duracion) y úsalo para planificar.
- Si menciona algo que tiene que llevar o recordar a futuro, guárdalo (guardar_memoria o \
programar_recordatorio).
- Cosas que llevar a una actividad: guardar_memoria con clave "llevar:<palabra del título del \
evento>" (p. ej. "llevar:entren", "llevar:eoi"); el aviso de "sal ya" las incluirá.
- Consulta leer_memoria cuando haga falta recordar algo que te contó antes.
- Gastos ("12 € Mercadona") -> anadir_gasto. Compras ("falta leche") -> anadir_compra.
- Nunca borres eventos que no sean del calendario Asistente. Confirma antes de borrar.
- Responde en 1–4 líneas. Sin rodeos.
"""


def _dt(texto: str) -> datetime:
    d = datetime.fromisoformat(texto)
    return d.replace(tzinfo=TZ) if d.tzinfo is None else d.astimezone(TZ)


def _fmt(d: datetime) -> str:
    return d.strftime("%a %d/%m %H:%M")


# ---------- Herramientas ----------

def t_ver_agenda(desde, hasta):
    evs = calendario.eventos(_dt(desde), _dt(hasta))
    return [
        {**e, "inicio": _fmt(e["inicio"]), "fin": e["fin"].strftime("%H:%M")}
        for e in evs
    ]


def t_buscar_huecos(desde, hasta, duracion_min, franjas=None):
    return [
        f"{_fmt(a)}–{b.strftime('%H:%M')}"
        for a, b in calendario.huecos_libres(_dt(desde), _dt(hasta), duracion_min, franjas)
    ]


def t_crear_evento(titulo, inicio, fin, avisos_min=None, notas="", lugar="", repetir=None):
    uid = calendario.crear_evento(
        titulo, _dt(inicio), _dt(fin), avisos_min if avisos_min is not None else [10], notas, lugar, repetir
    )
    return {"ok": True, "uid": uid}


def t_borrar_evento(uid):
    calendario.borrar_evento(uid)
    return {"ok": True}


def t_anadir_tarea(texto, fecha_limite=None, duracion_min=None):
    i, _ = db.ejecutar(
        "INSERT INTO tareas (texto, fecha_limite, duracion_min) VALUES (?,?,?)", texto, fecha_limite, duracion_min
    )
    return {"ok": True, "id": i}


def t_listar_tareas():
    return db.filas("SELECT id, texto, fecha_limite, duracion_min FROM tareas WHERE hecha=0 ORDER BY fecha_limite IS NULL, fecha_limite")


def t_completar_tarea(id):
    db.ejecutar("UPDATE tareas SET hecha=1 WHERE id=?", id)
    return {"ok": True}


def t_anadir_compra(items):
    for it in items:
        db.ejecutar("INSERT OR IGNORE INTO compras (item) VALUES (?)", it.strip().lower())
    return t_ver_compra()


def t_ver_compra():
    return [r["item"] for r in db.filas("SELECT item FROM compras ORDER BY id")]


def t_quitar_compra(items=None, todo=False):
    if todo:
        db.ejecutar("DELETE FROM compras")
    for it in items or []:
        db.ejecutar("DELETE FROM compras WHERE item=?", it.strip().lower())
    return t_ver_compra()


def t_anadir_gasto(importe, concepto, categoria=None, fecha=None):
    fecha = fecha or datetime.now(TZ).date().isoformat()
    db.ejecutar("INSERT INTO gastos (fecha, importe, concepto, categoria) VALUES (?,?,?,?)", fecha, importe, concepto, categoria)
    return {"ok": True}


def t_resumen_gastos(desde, hasta):
    total = db.filas("SELECT ROUND(SUM(importe),2) AS total FROM gastos WHERE fecha BETWEEN ? AND ?", desde, hasta)
    por_cat = db.filas(
        "SELECT COALESCE(categoria,'otros') AS categoria, ROUND(SUM(importe),2) AS total FROM gastos "
        "WHERE fecha BETWEEN ? AND ? GROUP BY 1 ORDER BY 2 DESC", desde, hasta)
    return {"total": total[0]["total"] or 0, "por_categoria": por_cat}


def t_registrar_duracion(actividad, minutos):
    db.ejecutar("INSERT INTO duraciones (actividad, minutos) VALUES (?,?)", actividad.lower(), minutos)
    return {"ok": True}


def t_estadisticas_duracion(actividad=None):
    if actividad:
        return db.filas(
            "SELECT actividad, COUNT(*) AS veces, ROUND(AVG(minutos)) AS media_min FROM duraciones "
            "WHERE actividad LIKE ? GROUP BY actividad", f"%{actividad.lower()}%")
    return db.filas("SELECT actividad, COUNT(*) AS veces, ROUND(AVG(minutos)) AS media_min FROM duraciones GROUP BY actividad")


def t_programar_recordatorio(cuando, texto):
    db.ejecutar("INSERT INTO recordatorios (cuando, texto) VALUES (?,?)", _dt(cuando).isoformat(), texto)
    return {"ok": True}


def t_guardar_memoria(clave, valor):
    db.ejecutar("INSERT OR REPLACE INTO memoria (clave, valor) VALUES (?,?)", clave.lower(), valor)
    return {"ok": True}


def t_leer_memoria():
    return db.filas("SELECT clave, valor FROM memoria")


FUNCIONES = {
    "ver_agenda": t_ver_agenda,
    "buscar_huecos": t_buscar_huecos,
    "crear_evento": t_crear_evento,
    "borrar_evento": t_borrar_evento,
    "anadir_tarea": t_anadir_tarea,
    "listar_tareas": t_listar_tareas,
    "completar_tarea": t_completar_tarea,
    "anadir_compra": t_anadir_compra,
    "ver_compra": t_ver_compra,
    "quitar_compra": t_quitar_compra,
    "anadir_gasto": t_anadir_gasto,
    "resumen_gastos": t_resumen_gastos,
    "registrar_duracion": t_registrar_duracion,
    "estadisticas_duracion": t_estadisticas_duracion,
    "programar_recordatorio": t_programar_recordatorio,
    "guardar_memoria": t_guardar_memoria,
    "leer_memoria": t_leer_memoria,
}

FECHA = {"type": "string", "description": "Fecha y hora local ISO, p. ej. 2026-11-09T16:00"}
DIA = {"type": "string", "description": "Fecha ISO, p. ej. 2026-11-09"}


def _tool(nombre, descripcion, props=None, requeridos=()):
    return {
        "name": nombre,
        "description": descripcion,
        "input_schema": {"type": "object", "properties": props or {}, "required": list(requeridos)},
    }


HERRAMIENTAS = [
    _tool("ver_agenda", "Eventos de todos sus calendarios entre dos momentos.", {"desde": FECHA, "hasta": FECHA}, ["desde", "hasta"]),
    _tool("buscar_huecos", "Huecos libres de al menos duracion_min, opcionalmente solo dentro de franjas.", {
        "desde": FECHA, "hasta": FECHA, "duracion_min": {"type": "integer"},
        "franjas": {"type": "array", "items": {"type": "object", "properties": {
            "dias": {"type": "array", "items": {"type": "integer"}, "description": "0=lunes … 6=domingo"},
            "inicio": {"type": "string", "description": "HH:MM"}, "fin": {"type": "string", "description": "HH:MM"}},
            "required": ["dias", "inicio", "fin"]}},
    }, ["desde", "hasta", "duracion_min"]),
    _tool("crear_evento", "Crea un evento en el calendario Asistente con avisos (minutos antes).", {
        "titulo": {"type": "string"}, "inicio": FECHA, "fin": FECHA,
        "avisos_min": {"type": "array", "items": {"type": "integer"}},
        "notas": {"type": "string"}, "lugar": {"type": "string"},
        "repetir": {"type": "string", "description": "RRULE opcional, p. ej. FREQ=WEEKLY;BYDAY=TU,TH"},
    }, ["titulo", "inicio", "fin"]),
    _tool("borrar_evento", "Borra un evento del calendario Asistente por uid.", {"uid": {"type": "string"}}, ["uid"]),
    _tool("anadir_tarea", "Apunta una tarea pendiente.", {"texto": {"type": "string"}, "fecha_limite": DIA, "duracion_min": {"type": "integer"}}, ["texto"]),
    _tool("listar_tareas", "Tareas pendientes."),
    _tool("completar_tarea", "Marca una tarea como hecha.", {"id": {"type": "integer"}}, ["id"]),
    _tool("anadir_compra", "Añade cosas a la lista de la compra.", {"items": {"type": "array", "items": {"type": "string"}}}, ["items"]),
    _tool("ver_compra", "Lista de la compra actual."),
    _tool("quitar_compra", "Quita cosas de la lista (o todo).", {"items": {"type": "array", "items": {"type": "string"}}, "todo": {"type": "boolean"}}),
    _tool("anadir_gasto", "Apunta un gasto en euros.", {"importe": {"type": "number"}, "concepto": {"type": "string"}, "categoria": {"type": "string"}, "fecha": DIA}, ["importe", "concepto"]),
    _tool("resumen_gastos", "Total y por categoría entre dos fechas.", {"desde": DIA, "hasta": DIA}, ["desde", "hasta"]),
    _tool("registrar_duracion", "Guarda cuánto tardó en una actividad.", {"actividad": {"type": "string"}, "minutos": {"type": "integer"}}, ["actividad", "minutos"]),
    _tool("estadisticas_duracion", "Media de minutos por actividad.", {"actividad": {"type": "string"}}),
    _tool("programar_recordatorio", "Le enviará un mensaje de Telegram a esa hora.", {"cuando": FECHA, "texto": {"type": "string"}}, ["cuando", "texto"]),
    _tool("guardar_memoria", "Guarda un dato duradero (p. ej. 'llevar:entreno' -> 'toalla, botella').", {"clave": {"type": "string"}, "valor": {"type": "string"}}, ["clave", "valor"]),
    _tool("leer_memoria", "Todos los datos guardados."),
]
HERRAMIENTAS[-1]["cache_control"] = {"type": "ephemeral"}


def _ejecutar(nombre, entrada):
    try:
        res = FUNCIONES[nombre](**entrada)
        return json.dumps(res, ensure_ascii=False, default=str), False
    except Exception as e:  # el error vuelve a Claude para que lo explique o reintente
        return f"Error: {e}", True


def responder(texto_usuario: str, guardar=True) -> str:
    """Una vuelta de conversación. Bloqueante: llamar desde un hilo."""
    ahora = datetime.now(TZ)
    contexto = f"[Ahora: {ahora.strftime('%A %d/%m/%Y %H:%M')} (hora de Canarias)]\n"
    mensajes = [
        {"role": "user" if h["rol"] == "user" else "assistant", "content": h["texto"]}
        for h in db.leer_historial()
    ]
    # El historial debe empezar por el usuario y alternar.
    while mensajes and mensajes[0]["role"] != "user":
        mensajes.pop(0)
    mensajes.append({"role": "user", "content": contexto + texto_usuario})

    for _ in range(12):
        r = client.beta.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=16000,
            system=PERFIL,
            tools=HERRAMIENTAS,
            messages=mensajes,
            thinking={"type": "adaptive"},
            output_config={"effort": ANTHROPIC_EFFORT},
            cache_control={"type": "ephemeral"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if r.stop_reason == "refusal":
            respuesta = "No puedo ayudarte con eso."
            break
        if r.stop_reason in ("end_turn", "max_tokens", "stop_sequence"):
            respuesta = "\n".join(b.text for b in r.content if b.type == "text").strip() or "Hecho."
            break
        mensajes.append({"role": "assistant", "content": r.content})
        if r.stop_reason == "pause_turn":
            continue
        resultados = []
        for b in r.content:
            if b.type == "tool_use":
                salida, error = _ejecutar(b.name, b.input)
                resultados.append({"type": "tool_result", "tool_use_id": b.id, "content": salida, "is_error": error})
        mensajes.append({"role": "user", "content": resultados})
    else:
        respuesta = "Me he liado con tantas consultas. ¿Me lo repites más concreto?"

    if guardar:
        db.guardar_historial("user", contexto + texto_usuario)
        db.guardar_historial("assistant", respuesta)
    return respuesta
