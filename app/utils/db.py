import sqlite3
from flask import current_app

def get_db_connection():
    conn = sqlite3.connect(current_app.config['DATABASE_PATH'])
    conn.execute("PRAGMA foreign_keys = ON;")  # OBLIGATORIO: Forzar integridad referencial
    conn.row_factory = sqlite3.Row
    return conn