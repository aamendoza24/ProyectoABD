import sqlite3
from app.utils.db import get_db_connection

class UsuarioRepository:
    """Maneja las operaciones de base de datos para la tabla usuarios y user_activity_log"""

    @staticmethod
    def obtener_usuario_por_username(username):
        conn = get_db_connection()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, user, email, contrasena, role, is_active, 
                       failed_login_attempts, account_locked, locked_until, IDEmpleado 
                FROM usuarios 
                WHERE user = ?
            """, (username,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def obtener_usuario_por_email(email):
        conn = get_db_connection()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, user, email, contrasena, role, is_active, IDEmpleado 
                FROM usuarios 
                WHERE email = ?
            """, (email,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def obtener_usuario_por_id(user_id):
        conn = get_db_connection()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM usuarios WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def obtener_usuario_por_token(token):
        conn = get_db_connection()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, reset_token_expiry 
                FROM usuarios 
                WHERE reset_token = ?
            """, (token,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def actualizar_logeo_exitoso(user_id, last_login_datetime_str):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE usuarios 
                SET failed_login_attempts = 0, last_login = ?, account_locked = 0, locked_until = NULL 
                WHERE id = ?
            """, (last_login_datetime_str, user_id))
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def actualizar_estado_bloqueo(user_id, intentos_fallidos, is_locked, lock_until_str=None):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE usuarios 
                SET failed_login_attempts = ?, account_locked = ?, locked_until = ? 
                WHERE id = ?
            """, (intentos_fallidos, 1 if is_locked else 0, lock_until_str, user_id))
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def actualizar_token_recuperacion(user_id, token, expiry_str):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE usuarios 
                SET reset_token = ?, reset_token_expiry = ? 
                WHERE id = ?
            """, (token, expiry_str, user_id))
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def actualizar_contrasena(user_id, hashed_pass):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE usuarios 
                SET contrasena = ?, reset_token = NULL, reset_token_expiry = NULL 
                WHERE id = ?
            """, (hashed_pass, user_id))
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def registrar_actividad(conn, user_id, activity_type, description, ip_address):
        """Si recibe la conexion (para transacciones compartidas) o abre una nueva si conn es None"""
        close_conn = False
        if not conn:
            conn = get_db_connection()
            close_conn = True
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_activity_log (user_id, activity_type, description, ip_address)
                VALUES (?, ?, ?, ?)
            """, (user_id, activity_type, description, ip_address))
            if close_conn:
                conn.commit()
        finally:
            if close_conn:
                conn.close()

    @staticmethod
    def crear_usuario(conn, username, email, hashed_password, role, is_active, empleado_id, created_at_str):
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO usuarios (user, email, contrasena, role, is_active, IDEmpleado, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (username, email, hashed_password, role, is_active, empleado_id, created_at_str))
        return cursor.lastrowid
        
    @staticmethod
    def actualizar_usuario(conn, user_id, username, email, role, is_active, hashed_password=None):
        cursor = conn.cursor()
        if hashed_password:
            cursor.execute("""
                UPDATE usuarios 
                SET user = ?, email = ?, contrasena = ?, role = ?, is_active = ?
                WHERE id = ?
            """, (username, email, hashed_password, role, is_active, user_id))
        else:
            cursor.execute("""
                UPDATE usuarios 
                SET user = ?, email = ?, role = ?, is_active = ?
                WHERE id = ?
            """, (username, email, role, is_active, user_id))
            
    @staticmethod
    def eliminar_log_y_usuario_por_id(conn, user_id):
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_activity_log WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM usuarios WHERE id = ?", (user_id,))

    @staticmethod
    def obtener_actividad_reciente(user_id, limit=10):
        conn = get_db_connection()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT activity_type, description, timestamp
                FROM user_activity_log
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (user_id, limit))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
