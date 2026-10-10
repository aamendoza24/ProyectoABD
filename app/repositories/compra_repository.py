from app.utils.db import get_db_connection
import sqlite3

class CompraRepository:
    """Repositorio transaccional e historico de compras"""

    @staticmethod
    def obtener_historial_compras(filtros=None):
        conexion = get_db_connection()
        try:
            conexion.row_factory = sqlite3.Row
            cursor = conexion.cursor()
            
            sql_query = """
                SELECT 
                    c.IDCompra,
                    c.Fecha,
                    c.Total,
                    (SELECT GROUP_CONCAT(DISTINCT p.Nombre) 
                     FROM Detalle_Compra dc 
                     JOIN Proveedor p ON dc.IDProveedor = p.IDProveedor 
                     WHERE dc.IDCompra = c.IDCompra) as proveedores,
                    (SELECT GROUP_CONCAT(DISTINCT s.Nombre) 
                     FROM Detalle_Compra dc 
                     JOIN Sucursal s ON dc.IDSucursal = s.IDSucursal 
                     WHERE dc.IDCompra = c.IDCompra) as sucursal,
                    (SELECT COUNT(*) FROM Detalle_Compra WHERE IDCompra = c.IDCompra) as num_productos
                FROM Compra c
            """
            
            conditions = []
            params = []
            
            if filtros:
                fecha_inicio = filtros.get('fecha_inicio')
                if fecha_inicio:
                    conditions.append("c.Fecha >= ?")
                    params.append(fecha_inicio)
                
                fecha_fin = filtros.get('fecha_fin')
                if fecha_fin:
                    conditions.append("c.Fecha <= ?")
                    params.append(fecha_fin)
                
                proveedor_id = filtros.get('proveedor_id')
                if proveedor_id:
                    conditions.append("c.IDCompra IN (SELECT DISTINCT IDCompra FROM Detalle_Compra WHERE IDProveedor = ?)")
                    params.append(proveedor_id)
                
                sucursal_id = filtros.get('sucursal_id')
                if sucursal_id:
                    conditions.append("c.IDCompra IN (SELECT DISTINCT IDCompra FROM Detalle_Compra WHERE IDSucursal = ?)")
                    params.append(sucursal_id)
                    
            if conditions:
                sql_query += " WHERE " + " AND ".join(conditions)
                
            sql_query += " ORDER BY c.Fecha DESC"
            
            cursor.execute(sql_query, params)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conexion.close()

    @staticmethod
    def obtener_compra_por_id(compra_id: int):
        conexion = get_db_connection()
        try:
            conexion.row_factory = sqlite3.Row
            cursor = conexion.cursor()
            cursor.execute("""
                SELECT 
                    c.IDCompra,
                    c.Fecha,
                    c.Total,
                    (SELECT GROUP_CONCAT(DISTINCT p.Nombre) 
                     FROM Detalle_Compra dc 
                     JOIN Proveedor p ON dc.IDProveedor = p.IDProveedor 
                     WHERE dc.IDCompra = c.IDCompra) as Proveedor,
                    (SELECT GROUP_CONCAT(DISTINCT s.Nombre) 
                     FROM Detalle_Compra dc 
                     JOIN Sucursal s ON dc.IDSucursal = s.IDSucursal 
                     WHERE dc.IDCompra = c.IDCompra) as Sucursal,
                    (SELECT Detalle FROM Detalle_Compra WHERE IDCompra = c.IDCompra LIMIT 1) as Detalle
                FROM Compra c
                WHERE c.IDCompra = ?
            """, (compra_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conexion.close()

    @staticmethod
    def obtener_detalles_compra(compra_id: int):
        conexion = get_db_connection()
        try:
            conexion.row_factory = sqlite3.Row
            cursor = conexion.cursor()
            cursor.execute("""
                SELECT 
                    dc.IDDetalleCompra,
                    p.Nombre as Producto,
                    p.IDProducto,
                    pr.Nombre as Proveedor,
                    pr.Telefono as telefono_proveedor,
                    pr.DireccionCompleta as direccion_proveedor,
                    s.Nombre as Sucursal,
                    s.Direccion as direccion_sucursal,
                    dc.Cantidad,
                    dc.Subtotal,
                    (dc.Subtotal / dc.Cantidad) as PrecioCompra
                FROM Detalle_Compra dc
                JOIN Producto p ON dc.IDProducto = p.IDProducto
                JOIN Proveedor pr ON dc.IDProveedor = pr.IDProveedor
                JOIN Sucursal s ON dc.IDSucursal = s.IDSucursal
                WHERE dc.IDCompra = ?
                ORDER BY p.Nombre
            """, (compra_id,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conexion.close()

    @staticmethod
    def crear_compra_cabecera(conexion, fecha: str, total: float):
        cursor = conexion.cursor()
        cursor.execute('INSERT INTO Compra (Fecha, Total) VALUES (?, ?)', (fecha, total))
        return cursor.lastrowid

    @staticmethod
    def guardar_detalle_compra(conexion, compra_id, producto_id, proveedor_id, sucursal_id, cantidad, subtotal, precio_compra, referencia):
        cursor = conexion.cursor()
        cursor.execute("""
            INSERT INTO Detalle_Compra 
            (IDCompra, IDProducto, IDProveedor, IDSucursal, Cantidad, Subtotal, PrecioCompra, Detalle) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (compra_id, producto_id, proveedor_id, sucursal_id, cantidad, subtotal, precio_compra, referencia))

    @staticmethod
    def actualizar_o_insertar_stock(conexion, sucursal_id, producto_id, cantidad):
        cursor = conexion.cursor()
        stock_existente = cursor.execute(
            'SELECT Cantidad FROM Stock_Sucursal WHERE IDSucursal = ? AND IDProducto = ?',
            (sucursal_id, producto_id)
        ).fetchone()

        if stock_existente:
            cursor.execute(
                'UPDATE Stock_Sucursal SET Cantidad = Cantidad + ? WHERE IDSucursal = ? AND IDProducto = ?',
                (cantidad, sucursal_id, producto_id)
            )
        else:
            cursor.execute(
                'INSERT INTO Stock_Sucursal (IDSucursal, IDProducto, Cantidad) VALUES (?, ?, ?)',
                (sucursal_id, producto_id, cantidad)
            )
