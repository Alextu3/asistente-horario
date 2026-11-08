"""Configuración: todo lo secreto llega por variables de entorno (Railway)."""
import os
from zoneinfo import ZoneInfo

TZ = ZoneInfo(os.environ.get("ZONA_HORARIA", "Atlantic/Canary"))

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
# Solo este usuario de Telegram puede hablar con el bot.
ALLOWED_USER_ID = int(os.environ["TELEGRAM_USER_ID"])

ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-5-5")
ANTHROPIC_EFFORT = os.environ.get("ANTHROPIC_EFFORT", "low")

ICLOUD_USER = os.environ.get("ICLOUD_USER", "")
ICLOUD_APP_PASSWORD = os.environ.get("ICLOUD_APP_PASSWORD", "")
CALENDARIO_BOT = os.environ.get("CALENDARIO_BOT", "Asistente")

DB_PATH = os.environ.get("DB_PATH", "/data/asistente.db")

# Minutos de trayecto en bus desde casa, por palabra clave en el título del evento.
TRAYECTOS = {
    "eoi": 45,
    "entren": 40,
    "misa": 60,
    "colegio": 20,
    "trabajo": 20,
}
MARGEN_SALIDA_MIN = 5  # aviso de "sal ya" con este margen extra

HORA_RESUMEN_MANANA = os.environ.get("HORA_RESUMEN_MANANA", "06:50")
HORA_REPASO_NOCHE = os.environ.get("HORA_REPASO_NOCHE", "22:15")
HORA_PLAN_SEMANAL = "19:00"  # domingos
