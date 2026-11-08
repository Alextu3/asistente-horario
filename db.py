"""Almacén local (SQLite): tareas, compras, gastos, duraciones, recordatorios, memoria."""
import os
import sqlite3
from contextlib import contextmanager

from config import DB_PATH

ESQUEMA = """
CREATE TABLE IF NOT EXISTS tareas (
  id INTEGER PRIMARY KEY, texto TEXT NOT NULL, fecha_limite TEXT,
  duracion_min INTEGER, hecha INTEGER DEFAULT 0, creada TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS compras (
  id INTEGER PRIMARY KEY, item TEXT NOT NULL UNIQUE, creada TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS gastos (
  id INTEGER PRIMARY KEY, fecha TEXT NOT NULL, importe REAL NOT NULL,
  concepto TEXT NOT NULL, categoria TEXT);
CREATE TABLE IF NOT EXISTS duraciones (
  id INTEGER PRIMARY KEY, actividad TEXT NOT NULL, minutos INTEGER NOT NULL,
  fecha TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS recordatorios (
  id INTEGER PRIMARY KEY, cuando TEXT NOT NULL, texto TEXT NOT NULL, enviado INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS memoria (
  clave TEXT PRIMARY KEY, valor TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS avisos_enviados (
  clave TEXT PRIMARY KEY, fecha TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS historial (
  id INTEGER PRIMARY KEY, rol TEXT NOT NULL, texto TEXT NOT NULL);
"""


def iniciar():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    with conexion() as c:
        c.executescript(ESQUEMA)


@contextmanager
def conexion():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def filas(sql, *args):
    with conexion() as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]


def ejecutar(sql, *args):
    with conexion() as c:
        cur = c.execute(sql, args)
        return cur.lastrowid, cur.rowcount


def aviso_ya_enviado(clave: str) -> bool:
    """Marca el aviso como enviado; devuelve True si ya lo estaba."""
    with conexion() as c:
        try:
            c.execute("INSERT INTO avisos_enviados (clave) VALUES (?)", (clave,))
            return False
        except sqlite3.IntegrityError:
            return True


def guardar_historial(rol: str, texto: str, maximo: int = 30):
    with conexion() as c:
        c.execute("INSERT INTO historial (rol, texto) VALUES (?, ?)", (rol, texto))
        c.execute(
            "DELETE FROM historial WHERE id NOT IN (SELECT id FROM historial ORDER BY id DESC LIMIT ?)",
            (maximo,),
        )


def leer_historial():
    return filas("SELECT rol, texto FROM historial ORDER BY id")
