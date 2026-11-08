"""Bot de Telegram: recibe mensajes de Alberto y le avisa de lo que toca."""
import asyncio
import logging
from datetime import datetime, time, timedelta

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

import agente
import calendario
import db
import horario
from config import (
    ALLOWED_USER_ID, HORA_PLAN_SEMANAL, HORA_REPASO_NOCHE, HORA_RESUMEN_MANANA,
    MARGEN_SALIDA_MIN, TELEGRAM_TOKEN, TRAYECTOS, TZ,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("asistente")
solo_alberto = filters.User(user_id=ALLOWED_USER_ID)


def _hora(texto: str) -> time:
    h, m = map(int, texto.split(":"))
    return time(h, m, tzinfo=TZ)


async def _enviar(ctx: ContextTypes.DEFAULT_TYPE, texto: str):
    await ctx.bot.send_message(chat_id=ALLOWED_USER_ID, text=texto)


async def _pensar(texto: str, guardar=True) -> str:
    return await asyncio.to_thread(agente.responder, texto, guardar)


# ---------- Mensajes de Alberto ----------

async def al_recibir(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await ctx.bot.send_chat_action(update.effective_chat.id, "typing")
    try:
        respuesta = await _pensar(update.message.text)
    except Exception:
        log.exception("Fallo al responder")
        respuesta = "⚠️ Algo ha fallado. Inténtalo de nuevo en un momento."
    await update.message.reply_text(respuesta)


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "¡Hola, Alberto! Escríbeme lo que quieras: citas, tareas, gastos, la compra, "
        "o cuánto has tardado en algo.\n\n/hoy – lo que te queda hoy\n/compra – lista de la compra\n"
        "/cargar_horario – crea tu horario semanal en el calendario Asistente (solo una vez)"
    )


async def cmd_hoy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(await _pensar("Dime en una lista corta lo que me queda hoy y qué tengo que llevar.", guardar=False))


async def cmd_compra(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    items = agente.t_ver_compra()
    await update.message.reply_text("🛒 " + (", ".join(items) if items else "La lista está vacía."))


async def cmd_cargar_horario(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if db.aviso_ya_enviado("horario_cargado"):
        await update.message.reply_text("El horario ya estaba cargado. Si quieres cambiarlo, dime qué.")
        return
    n = await asyncio.to_thread(horario.cargar)
    await update.message.reply_text(f"✅ He creado {n} bloques semanales en tu calendario Asistente.")


# ---------- Avisos automáticos ----------

def _trayecto(titulo: str):
    t = titulo.lower()
    for clave, minutos in TRAYECTOS.items():
        if clave in t:
            return minutos
    return None


def _que_llevar(titulo: str):
    t = titulo.lower()
    cosas = []
    for r in db.filas("SELECT clave, valor FROM memoria WHERE clave LIKE 'llevar:%'"):
        if r["clave"].split(":", 1)[1].strip() in t:
            cosas.append(r["valor"])
    return ", ".join(cosas)


async def revisar_cada_minuto(ctx: ContextTypes.DEFAULT_TYPE):
    ahora = datetime.now(TZ)
    # 1) Recordatorios programados
    for r in db.filas("SELECT id, cuando, texto FROM recordatorios WHERE enviado=0"):
        if datetime.fromisoformat(r["cuando"]) <= ahora:
            await _enviar(ctx, f"⏰ {r['texto']}")
            db.ejecutar("UPDATE recordatorios SET enviado=1 WHERE id=?", r["id"])

    # 2) Eventos: "sal ya" y "ahora toca"
    try:
        evs = await asyncio.to_thread(calendario.eventos, ahora - timedelta(minutes=1), ahora + timedelta(hours=2))
    except Exception:
        log.exception("No pude leer el calendario")
        return
    evs = [e for e in evs if not e["todo_el_dia"]]
    for i, e in enumerate(evs):
        clave = f"{e['uid']}|{e['inicio'].isoformat()}"
        trayecto = _trayecto(e["titulo"])
        if trayecto:
            salida = e["inicio"] - timedelta(minutes=trayecto + MARGEN_SALIDA_MIN)
            if salida <= ahora < e["inicio"] and not db.aviso_ya_enviado("salida|" + clave):
                llevar = _que_llevar(e["titulo"])
                msg = f"🚌 Sal ya hacia: {e['titulo']} ({e['inicio']:%H:%M}). Trayecto ~{trayecto} min."
                if llevar:
                    msg += f"\n🎒 Lleva: {llevar}"
                await _enviar(ctx, msg)
        if e["inicio"] <= ahora < e["inicio"] + timedelta(minutes=2) and not db.aviso_ya_enviado("ahora|" + clave):
            msg = f"▶️ Ahora: {e['titulo']} (hasta las {e['fin']:%H:%M})"
            siguiente = next((x for x in evs[i + 1:] if x["inicio"] >= e["fin"]), None)
            if siguiente:
                msg += f"\n⏭️ Después: {siguiente['titulo']} a las {siguiente['inicio']:%H:%M}"
            await _enviar(ctx, msg)


async def resumen_manana(ctx: ContextTypes.DEFAULT_TYPE):
    await _enviar(ctx, "☀️ " + await _pensar(
        "Buenos días. Hazme el resumen de hoy: agenda, a qué hora salir, qué llevar, tareas con fecha "
        "próxima y cualquier recordatorio. Muy breve.", guardar=False))


async def repaso_noche(ctx: ContextTypes.DEFAULT_TYPE):
    await _enviar(ctx, "🌙 Repaso del día: ¿qué hiciste de lo previsto y cuánto tardaste? "
                       "¿Algo pendiente para mañana? Contéstame cuando puedas.")


async def plan_semanal(ctx: ContextTypes.DEFAULT_TYPE):
    await _enviar(ctx, "🗓️ " + await _pensar(
        "Es domingo: prepárame la semana que viene. Resume la agenda, detecta choques, propón dónde "
        "colocar las tareas pendientes y dame el resumen de gastos de este mes. Breve.", guardar=True))


def main():
    db.iniciar()
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start, filters=solo_alberto))
    app.add_handler(CommandHandler("hoy", cmd_hoy, filters=solo_alberto))
    app.add_handler(CommandHandler("compra", cmd_compra, filters=solo_alberto))
    app.add_handler(CommandHandler("cargar_horario", cmd_cargar_horario, filters=solo_alberto))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & solo_alberto, al_recibir))

    jq = app.job_queue
    jq.run_repeating(revisar_cada_minuto, interval=60, first=5)
    jq.run_daily(resumen_manana, _hora(HORA_RESUMEN_MANANA))
    jq.run_daily(repaso_noche, _hora(HORA_REPASO_NOCHE))
    jq.run_daily(plan_semanal, _hora(HORA_PLAN_SEMANAL), days=(0,))  # en PTB, 0 = domingo

    log.info("Asistente en marcha")
    app.run_polling()


if __name__ == "__main__":
    main()
