from app.utils.db import get_db_connection
import sqlite3

class SucursalRepository:
    """Maneja el acceso a datos para la entidad Sucursal"""

    @staticmethod
    def obtener_todas_las_sucursales():
        """Obtiene la lista completa de sucursales"""
        conexion = get_db_connection()
        try:
            conexion.row_factory = sqlite3.Row
            cursor = conexion.cursor()
            cursor.execute("SELECT * FROM Sucursal ORDER BY Nombre")
            resultados = cursor.fetchall()
            return [dict(row) for row in resultados]
        finally:
            conexion.close()
