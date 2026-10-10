from app.utils.db import get_db_connection
import sqlite3
from datetime import datetime, timedelta

class ReporteRepository:
    """Maneja las consultas de estadísticas, KPIs y balance financiero general"""

    @staticmethod
    def obtener_ventas_agrupadas_por_fecha(fecha_inicio, fecha_fin):
        """Devuelve el total agrupado por día para gráficos (Dashboards)"""
        conexion = get_db_connection()
        try:
            conexion.row_factory = sqlite3.Row
            cursor = conexion.cursor()
            query = """
                SELECT DATE(Fecha) AS Fecha, SUM(Total) AS TotalVentas
                FROM Venta
            """
            params = []
            if fecha_inicio and fecha_fin:
                query += " WHERE DATE(Fecha) BETWEEN ? AND ?"
                params.extend([fecha_inicio, fecha_fin])
            query += " GROUP BY DATE(Fecha) ORDER BY DATE(Fecha)"
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conexion.close()

    @staticmethod
    def obtener_kpis_basicos(fecha_inicio, fecha_fin):
        """Devuelve sumatoria de ventas, cuenta de transacciones y ticket promedio (Dashboard)"""
        conexion = get_db_connection()
        try:
            conexion.row_factory = sqlite3.Row
            cursor = conexion.cursor()
            query = """
                SELECT SUM(Total) as TotalVentas, COUNT(*) as TotalTransacciones, AVG(Total) as TicketPromedio
                FROM Venta
            """
            params = []
            if fecha_inicio and fecha_fin:
                query += " WHERE DATE(Fecha) BETWEEN ? AND ?"
                params.extend([fecha_inicio, fecha_fin])
                
            cursor.execute(query, params)
            row = cursor.fetchone()
            return dict(row) if row else {"TotalVentas": 0, "TotalTransacciones": 0, "TicketPromedio": 0}
        finally:
            conexion.close()

    @staticmethod
    def obtener_top_productos(filtros, limit=5):
        """Top N productos más vendidos. 
        Puede filtrar por fechas, categoria, o sucursal.
        """
        conexion = get_db_connection()
        try:
            conexion.row_factory = sqlite3.Row
            cursor = conexion.cursor()
            
            where_conditions = []
            params = []
            
            if filtros.get('fecha_inicio') and filtros.get('fecha_fin'):
                where_conditions.append('DATE(v.Fecha) BETWEEN ? AND ?')
                params.extend([filtros['fecha_inicio'], filtros['fecha_fin']])
            elif filtros.get('recent_days'):
                where_conditions.append(f"DATE(v.Fecha) >= date('now', '-{filtros['recent_days']} days')")
                
            if filtros.get('id_categoria'):
                where_conditions.append('p.IDCategoria = ?')
                params.append(filtros['id_categoria'])
                
            if filtros.get('sucursal'):
                where_conditions.append('v.IDSucursal = ?')
                params.append(filtros['sucursal'])
                
            where_clause = 'WHERE ' + ' AND '.join(where_conditions) if where_conditions else ''
            
            query = f'''
                SELECT 
                    p.Nombre as Nombre,
                    c.Nombre as Categoria,
                    SUM(dv.Cantidad) as TotalVendido,
                    SUM(dv.Cantidad * dv.PrecioUnitario) as TotalVentas,
                    AVG(dv.PrecioUnitario) as PrecioPromedio
                FROM Detalle_Venta dv
                JOIN Producto p ON dv.IDProducto = p.IDProducto
                JOIN Categoria c ON p.IDCategoria = c.IDCategoria
                JOIN Venta v ON dv.IDVenta = v.IDVenta
                {where_clause}
                GROUP BY p.IDProducto, p.Nombre, c.Nombre
                ORDER BY TotalVentas DESC
                LIMIT ?
            '''
            params.append(limit)
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conexion.close()

    @staticmethod
    def obtener_ventas_recientes(limit=5):
        """Ultimos tickets registrados"""
        conexion = get_db_connection()
        try:
            conexion.row_factory = sqlite3.Row
            cursor = conexion.cursor()
            cursor.execute("""
                SELECT V.IDVenta as IDVenta, V.Fecha as Fecha, V.Total as Total, 
                       COALESCE(C.NombreCompleto, 'Cliente General') as Cliente
                FROM Venta V
                LEFT JOIN Cliente C ON V.IDCliente = C.IDCliente
                ORDER BY V.Fecha DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conexion.close()

    @staticmethod
    def obtener_kpi_general(tabla, columna, date_condition_str, param=None):
        """Consulta generica para sumatorias totales con una condicion de fechas embebida (SQLITE date math)"""
        conexion = get_db_connection()
        try:
            cursor = conexion.cursor()
            
            if param:
                query = f"SELECT SUM({columna}) FROM {tabla} WHERE {date_condition_str}"
                cursor.execute(query, (param,))
            else:
                query = f"SELECT SUM({columna}) FROM {tabla} WHERE {date_condition_str}"
                cursor.execute(query)
                
            res = cursor.fetchone()
            return res[0] if res and res[0] else 0
        finally:
            conexion.close()

    @staticmethod
    def contar_general(tabla, date_condition_str):
        """Cuenta filas bajo condiciones de fecha"""
        conexion = get_db_connection()
        try:
            cursor = conexion.cursor()
            query = f"SELECT COUNT(*) FROM {tabla} WHERE {date_condition_str}"
            cursor.execute(query)
            res = cursor.fetchone()
            return res[0] if res else 0
        finally:
            conexion.close()

    @staticmethod
    def obtener_promedio_general(tabla, columna, date_condition_str):
        """Obtiene promedios bajo condiciones de fecha"""
        conexion = get_db_connection()
        try:
            cursor = conexion.cursor()
            query = f"SELECT AVG({columna}) FROM {tabla} WHERE {date_condition_str}"
            cursor.execute(query)
            res = cursor.fetchone()
            return res[0] if res and res[0] else 0
        finally:
            conexion.close()

    @staticmethod
    def obtener_sum_join(table_1, table_2, join_on_1, join_on_2, columna_sumar, date_table, date_condition_str):
        """Consulta generica para JOIN con suma"""
        conexion = get_db_connection()
        try:
            cursor = conexion.cursor()
            query = f'''
                SELECT SUM({columna_sumar})
                FROM {table_1} t1
                JOIN {table_2} t2 ON t1.{join_on_1} = t2.{join_on_2}
                WHERE {date_table}.{date_condition_str}
            '''
            cursor.execute(query)
            res = cursor.fetchone()
            return res[0] if res and res[0] else 0
        finally:
            conexion.close()
            
    # ------ MÉTODOS PARA BALANCE (Ingreso, Egreso) ------
    
    @staticmethod
    def obtener_sumatoria_balance(table, where_clause, params):
        """Suma total de Venta o Compra"""
        conexion = get_db_connection()
        try:
            conexion.row_factory = sqlite3.Row
            query = f"SELECT COALESCE(SUM(Total), 0) as total FROM {table} {where_clause}"
            return conexion.execute(query, params).fetchone()['total']
        finally:
            conexion.close()

    @staticmethod
    def obtener_transacciones_ventas_balance(where_clause, params):
        conexion = get_db_connection()
        try:
            conexion.row_factory = sqlite3.Row
            query = f'''
                SELECT 
                    v.IDVenta as id,
                    v.Fecha as date,
                    'Venta' as type,
                    'Venta a ' || COALESCE(c.NombreCompleto, 'Cliente General') as description,
                    'Ventas' as category,
                    v.Total as income,
                    0 as expense,
                    v.Total as balance
                FROM Venta v
                LEFT JOIN Cliente c ON v.IDCliente = c.IDCliente
                {where_clause.replace('fecha', 'v.Fecha')}
            '''
            return [dict(row) for row in conexion.execute(query, params).fetchall()]
        finally:
            conexion.close()

    @staticmethod
    def obtener_transacciones_compras_balance(where_clause, params):
        conexion = get_db_connection()
        try:
            conexion.row_factory = sqlite3.Row
            query = f'''
                SELECT 
                    co.IDCompra as id,
                    co.Fecha as date,
                    'Compra' as type,
                    'Compra de inventario' as description,
                    'Compras' as category,
                    0 as income,
                    co.Total as expense,
                    -co.Total as balance
                FROM Compra co
                {where_clause.replace('fecha', 'co.Fecha')}
            '''
            return [dict(row) for row in conexion.execute(query, params).fetchall()]
        finally:
            conexion.close()
            
    @staticmethod
    def obtener_agrupados_por_periodo(table, date_trunc, where_clause, params):
        conexion = get_db_connection()
        try:
            conexion.row_factory = sqlite3.Row
            query = f'''
                SELECT 
                    {date_trunc} as period,
                    SUM(Total) as total
                FROM {table}
                {where_clause.replace('fecha', 'Fecha')}
                GROUP BY {date_trunc}
                ORDER BY period
            '''
            return [dict(row) for row in conexion.execute(query, params).fetchall()]
        finally:
            conexion.close()

    # ------ MÉTODOS PARA DASHBOARDS ESPECIALIZADOS DE COMPRAS ------
    @staticmethod
    def obtener_estadisticas_mensuales_compras():
        conexion = get_db_connection()
        try:
            conexion.row_factory = sqlite3.Row
            cursor = conexion.cursor()
            cursor.execute("""
                SELECT 
                    COUNT(DISTINCT c.IDCompra) as total_compras,
                    COALESCE(SUM(c.Total), 0) as monto_total,
                    COALESCE(AVG(c.Total), 0) as promedio_compra,
                    COALESCE(MAX(c.Total), 0) as compra_maxima,
                    COALESCE(MIN(c.Total), 0) as compra_minima,
                    COUNT(DISTINCT dc.IDProveedor) as total_proveedores,
                    COALESCE(SUM(dc.Cantidad), 0) as total_items
                FROM Compra c
                LEFT JOIN Detalle_Compra dc ON c.IDCompra = dc.IDCompra
                WHERE strftime('%Y-%m', c.Fecha) = strftime('%Y-%m', 'now')
            """)
            return dict(cursor.fetchone() or {})
        finally:
            conexion.close()
            
    @staticmethod
    def obtener_compras_recientes(limit=10):
        conexion = get_db_connection()
        try:
            conexion.row_factory = sqlite3.Row
            cursor = conexion.cursor()
            cursor.execute("""
                SELECT 
                    c.IDCompra,
                    c.Fecha,
                    c.Total,
                    COUNT(DISTINCT dc.IDProducto) as num_productos,
                    GROUP_CONCAT(DISTINCT p.Nombre) as proveedores,
                    s.Nombre as sucursal
                FROM Compra c
                LEFT JOIN Detalle_Compra dc ON c.IDCompra = dc.IDCompra
                LEFT JOIN Proveedor p ON dc.IDProveedor = p.IDProveedor
                LEFT JOIN Sucursal s ON dc.IDSucursal = s.IDSucursal
                WHERE c.Fecha >= date('now', '-30 days')
                GROUP BY c.IDCompra
                ORDER BY c.Fecha DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conexion.close()
            
    @staticmethod
    def obtener_grafico_compras_por_mes(seis_meses_atras):
        conexion = get_db_connection()
        try:
            conexion.row_factory = sqlite3.Row
            cursor = conexion.cursor()
            cursor.execute("""
                SELECT 
                    strftime('%Y-%m', c.Fecha) as mes,
                    SUM(c.Total) as total
                FROM Compra c
                WHERE c.Fecha >= ?
                GROUP BY strftime('%Y-%m', c.Fecha)
                ORDER BY mes
            """, (seis_meses_atras,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conexion.close()

    @staticmethod
    def obtener_grafico_compras_por_proveedor(seis_meses_atras):
        conexion = get_db_connection()
        try:
            conexion.row_factory = sqlite3.Row
            cursor = conexion.cursor()
            cursor.execute("""
                SELECT 
                    p.Nombre as proveedor,
                    SUM(dc.Subtotal) as total
                FROM Detalle_Compra dc
                JOIN Proveedor p ON dc.IDProveedor = p.IDProveedor
                JOIN Compra c ON dc.IDCompra = c.IDCompra
                WHERE c.Fecha >= ?
                GROUP BY p.IDProveedor
                ORDER BY total DESC
                LIMIT 5
            """, (seis_meses_atras,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conexion.close()

    @staticmethod
    def obtener_grafico_compras_por_sucursal(seis_meses_atras):
        conexion = get_db_connection()
        try:
            conexion.row_factory = sqlite3.Row
            cursor = conexion.cursor()
            cursor.execute("""
                SELECT 
                    s.Nombre as sucursal,
                    SUM(dc.Subtotal) as total
                FROM Detalle_Compra dc
                JOIN Sucursal s ON dc.IDSucursal = s.IDSucursal
                JOIN Compra c ON dc.IDCompra = c.IDCompra
                WHERE c.Fecha >= ?
                GROUP BY s.IDSucursal
                ORDER BY total DESC
            """, (seis_meses_atras,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conexion.close()

    @staticmethod
    def obtener_top_productos_comprados(seis_meses_atras, limit=10):
        conexion = get_db_connection()
        try:
            conexion.row_factory = sqlite3.Row
            cursor = conexion.cursor()
            cursor.execute("""
                SELECT 
                    p.Nombre as producto,
                    SUM(dc.Cantidad) as cantidad,
                    SUM(dc.Subtotal) as total
                FROM Detalle_Compra dc
                JOIN Producto p ON dc.IDProducto = p.IDProducto
                JOIN Compra c ON dc.IDCompra = c.IDCompra
                WHERE c.Fecha >= ?
                GROUP BY p.IDProducto
                ORDER BY cantidad DESC
                LIMIT ?
            """, (seis_meses_atras, limit))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conexion.close()
