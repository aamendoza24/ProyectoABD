import sqlite3
from app.utils.db import get_db_connection

class EmpleadoRepository:
    """Maneja las operaciones de base de datos para la tabla Empleado, Cargos e integraciones con usuarios"""

    @staticmethod
    def obtener_empleados_detallados():
        """Obtiene la lista de empleados con sus relaciones (Cargo, Usuario, Sucursal)"""
        conn = get_db_connection()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT e.IDEmpleado, e.NombreCompleto, c.Nombre as cargo_nombre, e.IDCargo,
                       u.id as user_id, u.user, u.email, u.role, u.is_active, u.account_locked,
                       u.last_login, s.Nombre as sucursal_nombre, s.IDSucursal
                FROM Empleado e
                LEFT JOIN usuarios u ON e.IDEmpleado = u.IDEmpleado
                LEFT JOIN Cargo c ON e.IDCargo = c.IDCargo
                LEFT JOIN Sucursal s ON 1=1  -- Hack heredado en caso de manejar una sola sucursal genérica
                ORDER BY e.NombreCompleto
            """)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def obtener_empleado_detallado_por_id(empleado_id):
        conn = get_db_connection()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT e.IDEmpleado, e.NombreCompleto, c.Nombre as cargo_nombre, e.IDCargo,
                       u.id as user_id, u.user, u.email, u.role, u.is_active, u.account_locked,
                       u.last_login, s.Nombre as sucursal_nombre, s.IDSucursal
                FROM Empleado e
                LEFT JOIN usuarios u ON e.IDEmpleado = u.IDEmpleado
                LEFT JOIN Cargo c ON e.IDCargo = c.IDCargo
                LEFT JOIN Sucursal s ON 1=1
                WHERE e.IDEmpleado = ?
            """, (empleado_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def obtener_empleado_simple_por_id(empleado_id):
        conn = get_db_connection()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT IDEmpleado FROM Empleado WHERE IDEmpleado = ?", (empleado_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def obtener_cargos():
        conn = get_db_connection()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT IDCargo, Nombre FROM Cargo ORDER BY Nombre")
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def obtener_usuario_cruzado_existente(username, email, empleado_id=None):
        """Verifica si username o email existen en otro usuario diferente al empleado_id provisto"""
        conn = get_db_connection()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if empleado_id:
                cursor.execute("""
                    SELECT id FROM usuarios 
                    WHERE (user = ? OR email = ?) AND IDEmpleado != ?
                """, (username, email, empleado_id))
            else:
                cursor.execute("SELECT id FROM usuarios WHERE user = ? OR email = ?", (username, email))
            
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def crear_empleado(conn, nombre_completo, cargo_id):
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Empleado (NombreCompleto, IDCargo)
            VALUES (?, ?)
        """, (nombre_completo, cargo_id))
        return cursor.lastrowid

    @staticmethod
    def actualizar_empleado(conn, empleado_id, nombre_completo, cargo_id):
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE Empleado 
            SET NombreCompleto = ?, IDCargo = ?
            WHERE IDEmpleado = ?
        """, (nombre_completo, cargo_id, empleado_id))

    @staticmethod
    def eliminar_empleado(conn, empleado_id):
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Empleado WHERE IDEmpleado = ?", (empleado_id,))
