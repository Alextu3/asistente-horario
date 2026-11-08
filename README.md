# Asistente de horario (bot de Telegram)

Asistente personal de Alberto: organiza el horario en el Calendario de Apple (iCloud), avisa de lo que toca,
de cuándo salir y qué llevar, y lleva tareas, lista de la compra, gastos y tiempos reales de cada actividad.

## Qué hace
- **Conversación libre** por Telegram ("un padre quiere cita", "falta leche", "12 € Mercadona",
  "corregir me llevó 40 min"). Claude usa herramientas para leer/escribir el calendario y la base de datos.
- **Avisos automáticos** (revisión cada minuto):
  - "▶️ Ahora: …" al empezar cada evento, con lo siguiente.
  - "🚌 Sal ya" según el trayecto (EOI 45 min, entrenamiento 40, misa 60, colegio 20) + qué llevar.
  - Recordatorios puntuales que programes ("recuérdame llamar al dentista mañana a las 10").
- **Resumen** a las 06:50, **repaso nocturno** a las 22:15 y **plan semanal** los domingos a las 19:00.
- `/cargar_horario` crea el horario semanal acordado (estudio, paseos, deporte) en el calendario *Asistente*.

## Variables de entorno (en Railway → Variables)
| Variable | Valor |
|---|---|
| `TELEGRAM_TOKEN` | token de @BotFather |
| `TELEGRAM_USER_ID` | tu ID numérico (de @userinfobot) |
| `ANTHROPIC_API_KEY` | clave `sk-ant-…` |
| `ICLOUD_USER` | tu Apple ID (correo) |
| `ICLOUD_APP_PASSWORD` | contraseña de aplicación de iCloud |
| `DB_PATH` | `/data/asistente.db` |

Opcionales: `CALENDARIO_BOT` (por defecto `Asistente`), `ANTHROPIC_MODEL` (por defecto `claude-opus-5-5`),
`ANTHROPIC_EFFORT` (por defecto `low`), `HORA_RESUMEN_MANANA`, `HORA_REPASO_NOCHE`.

## Despliegue en Railway
1. *New Project → Deploy from GitHub repo →* `asistente-horario`.
2. En el servicio: *Variables* → añade las de la tabla.
3. *Settings → Volumes → Add volume*, montado en `/data` (para no perder tareas y gastos).
4. Railway arranca con `python bot.py` (ver `railway.json`).
5. En Telegram, abre tu bot, pulsa *Iniciar* y escribe `/cargar_horario`.

## Para que el reloj vibre
- iPhone → Ajustes → Notificaciones → Telegram: activadas.
- App Watch → Notificaciones → Telegram: "Replicar iPhone".
- Los eventos del calendario *Asistente* llevan aviso propio, así que también vibran por el Calendario.

## Ajustes rápidos
- Trayectos y palabras clave: `TRAYECTOS` en `config.py`.
- Bloques del horario: `BLOQUES` en `horario.py`.
- Qué llevar: dile al bot "para el entreno llevo toalla y botella" (lo guarda como `llevar:entren`).
