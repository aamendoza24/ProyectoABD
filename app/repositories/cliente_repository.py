from app.utils.db import get_db_connection
import sqlite3

class ClienteRepository:
    """Maneja el acceso a datos para la entidad Cliente"""

    @staticmethod
    def obtener_todos_los_clientes():
        """Obtiene la lista completa de clientes (ID y Nombre)"""
        conexion = get_db_connection()
        try:
            conexion.row_factory = sqlite3.Row
            cursor = conexion.cursor()
            cursor.execute("SELECT IDCliente, NombreCompleto FROM Cliente ORDER BY NombreCompleto")
            resultados = cursor.fetchall()
            return [dict(row) for row in resultados]
        finally:
            conexion.close()

    @staticmethod
    def buscar_clientes_por_termino(termino: str):
        """Busca clientes por coincidencia de nombre o teléfono"""
        conexion = get_db_connection()
        try:
            conexion.row_factory = sqlite3.Row
            cursor = conexion.cursor()
            query = """
            SELECT IDCliente, NombreCompleto, Telefono, Email 
            FROM Cliente 
            WHERE NombreCompleto LIKE ? OR Telefono LIKE ?
            LIMIT 10
            """
            search_term = f'%{termino}%'
            cursor.execute(query, (search_term, search_term))
            resultados = cursor.fetchall()
            return [dict(row) for row in resultados]
        finally:
            conexion.close()

    @staticmethod
    def crear_cliente_con_conexion(nombre: str, telefono: str, conexion):
        """
        Inserta un nuevo cliente en la base de datos usando una conexión proporcionada.
        Útil para transacciones complejas.
        Devuelve el ID del nuevo cliente.
        """
        cursor = conexion.cursor()
        cursor.execute("""
            INSERT INTO Cliente (NombreCompleto, Telefono) VALUES (?, ?)
        """, (nombre, telefono))
        return cursor.lastrowid
