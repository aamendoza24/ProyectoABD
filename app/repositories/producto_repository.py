from app.utils.db import get_db_connection

class ProductoRepository:
    
    @staticmethod
    def buscar_productos_por_nombre(query):
        conexion = get_db_connection()
        try:
            cursor = conexion.cursor()
            cursor.execute("SELECT IDProducto, Nombre FROM Producto WHERE Nombre LIKE ?", (f"%{query}%",))
            # Convertimos sqlite3.Row explícitamente a dict dict() para evitar ataduras a SQLite a largo plazo
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conexion.close()

    @staticmethod
    def obtener_stock_completo():
        conexion = get_db_connection()
        try:
            cursor = conexion.cursor()
            cursor.execute("""
                SELECT 
                    p.IDProducto, 
                    p.Nombre, 
                    p.Precio AS precio_venta, 
                    p.ImagenURL, 
                    p.IDCategoria, 
                    c.Nombre AS nombre_categoria, 
                    COALESCE(s.Cantidad, 0) AS stock_total,
                    COALESCE((
                        SELECT (dc.Subtotal / CASE WHEN dc.Cantidad = 0 THEN 1 ELSE CAST(dc.Cantidad AS REAL) END)
                        FROM Detalle_Compra dc
                        JOIN Compra co ON dc.IDCompra = co.IDCompra
                        WHERE dc.IDProducto = p.IDProducto
                        ORDER BY co.Fecha DESC, dc.IDDetalleCompra DESC
                        LIMIT 1
                    ), 0.0) AS precio_compra,
                    p.Descripcion
                FROM Producto AS p
                LEFT JOIN Categoria AS c ON p.IDCategoria = c.IDCategoria
                LEFT JOIN Stock_Sucursal AS s ON p.IDProducto = s.IDProducto AND s.IDSucursal = 1
            """)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conexion.close()

    @staticmethod
    def obtener_producto_por_id(producto_id):
        conexion = get_db_connection()
        try:
            cursor = conexion.cursor()
            cursor.execute(
                """SELECT p.IDProducto, p.Nombre, p.Precio AS precio_venta, p.ImagenURL, 
                          p.IDCategoria, c.Nombre AS nombre_categoria,
                          COALESCE(s.Cantidad, 0) AS stock_total, 
                          p.Descripcion
                   FROM Producto p 
                   LEFT JOIN Categoria c ON p.IDCategoria = c.IDCategoria
                   LEFT JOIN Stock_Sucursal s ON p.IDProducto = s.IDProducto AND s.IDSucursal = 1
                   WHERE p.IDProducto = ?""",
                (producto_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conexion.close()

    @staticmethod
    def obtener_categorias():
        conexion = get_db_connection()
        try:
            cursor = conexion.cursor()
            cursor.execute("SELECT IDCategoria, Nombre FROM Categoria")
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conexion.close()

    @staticmethod
    def verificar_producto_existe(producto_id):
        conexion = get_db_connection()
        try:
            cursor = conexion.cursor()
            cursor.execute("SELECT 1 FROM Producto WHERE IDProducto = ?", (producto_id,))
            return cursor.fetchone() is not None
        finally:
            conexion.close()

    @staticmethod
    def crear_producto(categoria_id, nombre, descripcion, precio, imagen_url, stock_inicial=0):
        conexion = get_db_connection()
        try:
            cursor = conexion.cursor()
            cursor.execute("""
                INSERT INTO Producto (IDCategoria, Nombre, Descripcion, Precio, ImagenURL)
                VALUES (?, ?, ?, ?, ?)
            """, (categoria_id, nombre, descripcion, precio, imagen_url))
            
            producto_id = cursor.lastrowid
            
            if int(stock_inicial) >= 0:
                cursor.execute("""
                    INSERT INTO Stock_Sucursal (IDSucursal, IDProducto, Cantidad)
                    VALUES (?, ?, ?)
                """, (1, producto_id, stock_inicial))
                
            conexion.commit()
            return producto_id
        except Exception as e:
            conexion.rollback()
            raise e
        finally:
            conexion.close()

    @staticmethod
    def actualizar_producto(producto_id, nombre, precio, categoria_id, descripcion, imagen_url=None, actualizar_imagen=False):
        conexion = get_db_connection()
        try:
            cursor = conexion.cursor()
            
            update_fields = [
                "Nombre = ?", 
                "Precio = ?", 
                "IDCategoria = ?", 
                "Descripcion = ?"
            ]
            
            params = [nombre, precio, categoria_id, descripcion]
            
            if actualizar_imagen:
                update_fields.append("ImagenURL = ?")
                params.append(imagen_url)
                
            params.append(producto_id)
            
            cursor.execute(f"""
                UPDATE Producto 
                SET {', '.join(update_fields)}
                WHERE IDProducto = ?
            """, params)
            
            conexion.commit()
        except Exception as e:
            conexion.rollback()
            raise e
        finally:
            conexion.close()
