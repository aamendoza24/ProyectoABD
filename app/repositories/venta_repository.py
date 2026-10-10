from app.utils.db import get_db_connection
import sqlite3
from datetime import datetime, timedelta, date

class VentaRepository:
    """Maneja el acceso a datos transaccional de ventas y su catálogo"""

    @staticmethod
    def obtener_catalogo_para_venta(id_sucursal: int = 1):
        """Obtiene productos con stock disponible para la venta"""
        conexion = get_db_connection()
        try:
            conexion.row_factory = sqlite3.Row
            cursor = conexion.cursor()
            cursor.execute("""
                SELECT Producto.IDProducto, Nombre, Precio, ImagenURL, 
                       IDCategoria, Stock_Sucursal.Cantidad 
                FROM Producto
                JOIN Stock_Sucursal ON Producto.IDProducto = Stock_Sucursal.IDProducto
                WHERE Stock_Sucursal.IDSucursal = ?
            """, (id_sucursal,))
            productos = cursor.fetchall()

            cursor.execute("SELECT IDCategoria, Nombre FROM Categoria")
            categorias = cursor.fetchall()
            
            return [dict(p) for p in productos], [dict(c) for c in categorias]
        finally:
            conexion.close()

    @staticmethod
    def crear_venta_cabecera(conexion, fecha: str, total: float, id_empleado: int, 
                            id_cliente: int, id_sucursal: int, metodo_pago: str, descuento: float):
        """Registra la cabecera de la venta en la base de datos"""
        cursor = conexion.cursor()
        cursor.execute("""
            INSERT INTO Venta (Fecha, Total, IDEmpleado, IDCliente, IDSucursal, MetodoPago, Descuento)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (fecha, total, id_empleado, id_cliente, id_sucursal, metodo_pago, descuento))
        return cursor.lastrowid

    @staticmethod
    def guardar_detalle_venta(conexion, id_venta: int, id_producto: int, 
                            cantidad: int, precio_unitario: float, subtotal: float):
        """Registra un producto individual dentro de una venta"""
        cursor = conexion.cursor()
        cursor.execute("""
            INSERT INTO Detalle_Venta (IDVenta, IDProducto, Cantidad, PrecioUnitario, Subtotal)
            VALUES (?, ?, ?, ?, ?)
        """, (id_venta, id_producto, cantidad, precio_unitario, subtotal))

    @staticmethod
    def descontar_stock(conexion, id_producto: int, cantidad: int, id_sucursal: int):
        """Descuenta de inventario el producto tras una venta"""
        cursor = conexion.cursor()
        cursor.execute("""
            UPDATE Stock_Sucursal SET Cantidad = Cantidad - ?
            WHERE IDProducto = ? AND IDSucursal = ?
        """, (cantidad, id_producto, id_sucursal))

    @staticmethod
    def obtener_ventas_filtradas(filtro: str, fecha_inicio=None, fecha_fin=None, cliente_id=None):
        """Obtiene la lista de ventas basada en filtros (historial)"""
        conexion = get_db_connection()
        try:
            conexion.row_factory = sqlite3.Row
            cursor = conexion.cursor()
            
            query = """
                SELECT v.IDVenta as id, v.Fecha as fecha, v.Total as total, 
                       COALESCE(c.NombreCompleto, 'Cliente General') as cliente
                FROM Venta v
                LEFT JOIN Cliente c ON v.IDCliente = c.IDCliente
                WHERE 1=1
            """
            params = []
            
            if filtro == "hoy":
                query += " AND DATE(v.Fecha) = ?"
                params.append(date.today().strftime('%Y-%m-%d'))
            elif filtro == "semana":
                fecha_limite = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
                query += " AND v.Fecha >= ?"
                params.append(fecha_limite)
            elif filtro == "mes":
                fecha_limite = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
                query += " AND v.Fecha >= ?"
                params.append(fecha_limite)
            elif filtro == "personalizado":
                if fecha_inicio:
                    query += " AND DATE(v.Fecha) >= ?"
                    params.append(fecha_inicio)
                if fecha_fin:
                    query += " AND DATE(v.Fecha) <= ?"
                    params.append(fecha_fin)
                if cliente_id:
                    query += " AND v.IDCliente = ?"
                    params.append(cliente_id)
                    
            query += " ORDER BY v.Fecha DESC"
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conexion.close()

    @staticmethod
    def obtener_venta_por_id(id_venta: int):
        """Obtiene una Venta agrupada con su información cabecera"""
        conexion = get_db_connection()
        try:
            conexion.row_factory = sqlite3.Row
            cursor = conexion.cursor()
            cursor.execute("""
                SELECT v.IDVenta as id, v.Fecha as fecha, v.Total as total, 
                       COALESCE(c.NombreCompleto, 'Cliente General') as cliente, 
                       COALESCE(v.MetodoPago, 'efectivo') as metodo_pago, 
                       COALESCE(v.Descuento, 0) as descuento,
                       COALESCE(e.NombreCompleto, 'No registrado') as empleado
                FROM Venta v
                LEFT JOIN Cliente c ON v.IDCliente = c.IDCliente
                LEFT JOIN Empleado e ON v.IDEmpleado = e.IDEmpleado
                WHERE v.IDVenta = ?
            """, (id_venta,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conexion.close()

    @staticmethod
    def obtener_detalles_venta(id_venta: int):
        """Obtiene la lista de los productos despachados en una venta"""
        conexion = get_db_connection()
        try:
            conexion.row_factory = sqlite3.Row
            cursor = conexion.cursor()
            cursor.execute("""
                SELECT Producto.Nombre as nombre, 
                       Detalle_Venta.Cantidad as cantidad, 
                       Detalle_Venta.PrecioUnitario as precio_unitario,
                       Detalle_Venta.Subtotal as subtotal
                FROM Detalle_Venta
                JOIN Producto ON Detalle_Venta.IDProducto = Producto.IDProducto
                WHERE Detalle_Venta.IDVenta = ?
            """, (id_venta,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conexion.close()
