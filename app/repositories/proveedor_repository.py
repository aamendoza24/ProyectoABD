from app.utils.db import get_db_connection
import sqlite3

class ProveedorRepository:
    """Maneja el acceso a datos para la entidad Proveedor"""

    @staticmethod
    def obtener_todos_los_proveedores():
        """Obtiene la lista completa de proveedores para populares selects"""
        conexion = get_db_connection()
        try:
            conexion.row_factory = sqlite3.Row
            cursor = conexion.cursor()
            cursor.execute("SELECT * FROM Proveedor ORDER BY Nombre")
            resultados = cursor.fetchall()
            return [dict(row) for row in resultados]
        finally:
            conexion.close()

    @staticmethod
    def crear_proveedor(nombre, telefono, email, direccion):
        conexion = get_db_connection()
        try:
            cursor = conexion.cursor()
            cursor.execute("""
                INSERT INTO Proveedor (Nombre, Telefono, Email, DireccionCompleta)
                VALUES (?, ?, ?, ?)""",
                (nombre, telefono, email, direccion))
            conexion.commit()
            return cursor.lastrowid
        finally:
            conexion.close()

    @staticmethod
    def actualizar_proveedor(proveedor_id, nombre, telefono, email, direccion):
        conexion = get_db_connection()
        try:
            cursor = conexion.cursor()
            cursor.execute("""
                UPDATE Proveedor 
                SET Nombre = ?, Telefono = ?, Email = ?, DireccionCompleta = ?
                WHERE IDProveedor = ?""",
                (nombre, telefono, email, direccion, proveedor_id))
            conexion.commit()
        finally:
            conexion.close()

    @staticmethod
    def eliminar_proveedor(proveedor_id):
        conexion = get_db_connection()
        try:
            cursor = conexion.cursor()
            cursor.execute("DELETE FROM Proveedor WHERE IDProveedor = ?", (proveedor_id,))
            conexion.commit()
        finally:
            conexion.close()

    @staticmethod
    def verificar_compras_asociadas(proveedor_id):
        conexion = get_db_connection()
        try:
            conexion.row_factory = sqlite3.Row
            cursor = conexion.cursor()
            res = cursor.execute("""
                SELECT COUNT(*) as total FROM Detalle_Compra WHERE IDProveedor = ?""",
                (proveedor_id,)).fetchone()
            return res['total'] > 0 if res else False
        finally:
            conexion.close()

    @staticmethod
    def obtener_proveedor_por_id(proveedor_id):
        conexion = get_db_connection()
        try:
            conexion.row_factory = sqlite3.Row
            cursor = conexion.cursor()
            res = cursor.execute("SELECT * FROM Proveedor WHERE IDProveedor = ?", (proveedor_id,)).fetchone()
            return dict(res) if res else None
        finally:
            conexion.close()

    @staticmethod
    def obtener_compras_recientes_proveedor(proveedor_id, limit=5):
        conexion = get_db_connection()
        try:
            conexion.row_factory = sqlite3.Row
            cursor = conexion.cursor()
            compras = cursor.execute("""
                SELECT c.IDCompra, c.Fecha, c.Total
                FROM Compra c
                JOIN Detalle_Compra dc ON c.IDCompra = dc.IDCompra
                WHERE dc.IDProveedor = ?
                ORDER BY c.Fecha DESC
                LIMIT ?
            """, (proveedor_id, limit)).fetchall()
            return [dict(c) for c in compras]
        finally:
            conexion.close()
