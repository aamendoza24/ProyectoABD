from flask import Blueprint, render_template, request, flash, jsonify
from datetime import datetime, timedelta, date
from app.utils.db import get_db_connection
from app.utils import login_required, role_required
from app.blueprints.ventas import ventas_bp

#ventas_bp = Blueprint('ventas', __name__, url_prefix='')


#ruta para mostrar los productos en el apartado de venta
@ventas_bp.route('/catalogo')
def catalogo():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""SELECT Producto.IDProducto, Nombre, Precio, ImagenURL, 
                        IDCategoria, Stock_Sucursal.Cantidad FROM Producto
                   JOIN Stock_Sucursal ON Producto.IDProducto = Stock_Sucursal.IDProducto
                   Where Stock_Sucursal.IDSucursal = 1""")
    productos = cursor.fetchall()
    cursor.execute("SELECT IDCategoria, Nombre FROM Categoria")
    categorias = cursor.fetchall()
    print(productos)
    print(categorias)

    return render_template("ventas/realizar_venta.html", productos=productos, categorias=categorias)


@ventas_bp.route("/guardar_venta", methods=["POST"])
def guardar_venta():
    data = request.get_json()

    productos = data.get("carrito", [])
    total = data.get("total")
    descuento = data.get("descuento", 0)
    tipo_pago = data.get("tipo_pago")
    cliente_nombre = data.get("cliente_nombre")
    cliente_id = data.get("cliente_id")
    cambio = data.get("cambio", 0)
    nota = data.get("nota", "")
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        db = get_db_connection()
        cursor = db.cursor()

        # Insertar la venta
        cursor.execute("""
            INSERT INTO Venta (Fecha, Total)
            VALUES (?, ?)
        """, (fecha, total))
        venta_id = cursor.lastrowid

        # Insertar los productos vendidos
        print(productos)
        for producto in productos:
            print("Producto insertado ", producto)
            cursor.execute("""
                INSERT INTO Detalle_Venta (IDVenta, IDProducto, Cantidad, PrecioUnitario, Subtotal)
                VALUES (?, ?, ?, ?, ?)
            """, (venta_id, producto["id"], producto["cantidad"], producto["precio"], producto["cantidad"] * producto["precio"] ))


            #Actualizacion del stock de productos
            cursor.execute("UPDATE Stock_Sucursal SET Cantidad = Cantidad - ? WHERE IDProducto = ?", (producto["cantidad"], producto["id"]))


        db.commit()
        return jsonify({"success": True, "mensaje": "Venta guardada exitosamente"}), 200

    except Exception as e:
        print("Error:", e)
        return jsonify({"error": "No se pudo guardar la venta"}), 500


def obtener_ventas(filtro, fecha_inicio=None, fecha_fin=None, cliente_id=None):
    """Obtiene las ventas según los filtros aplicados"""
    conexion = get_db_connection()
    cursor = conexion.cursor()
    
    # Construir la consulta base
    query = """
        SELECT v.IDVenta, v.Fecha, v.Total, COALESCE(c.NombreCompleto, 'Cliente General') as cliente
        FROM Venta v
        LEFT JOIN Cliente c ON v.IDCliente = c.IDCliente
        WHERE 1=1
    """
    params = []
    
    # Aplicar filtros predefinidos
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
    
    # Aplicar filtros personalizados
    if filtro == "personalizado":
        if fecha_inicio:
            query += " AND DATE(v.Fecha) >= ?"
            params.append(fecha_inicio)
        
        if fecha_fin:
            query += " AND DATE(v.Fecha) <= ?"
            params.append(fecha_fin)
        
        if cliente_id:
            query += " AND v.IDCliente = ?"
            params.append(cliente_id)
    
    # Ordenar por fecha descendente
    query += " ORDER BY v.Fecha DESC"
    
    cursor.execute(query, params)
    
    ventas = [{"id": row[0], "fecha": row[1], "total": row[2], "cliente": row[3]} for row in cursor.fetchall()]
    conexion.close()
    return ventas

def obtener_clientes():
    """Obtiene la lista de clientes para el filtro"""
    conexion = get_db_connection()
    cursor = conexion.cursor()
    
    cursor.execute("SELECT IDCliente, NombreCompleto FROM Cliente ORDER BY NombreCompleto")
    clientes = [{"IDCliente": row[0], "NombreCompleto": row[1]} for row in cursor.fetchall()]
    
    conexion.close()
    return clientes

@ventas_bp.route("/historial", methods=["GET", "POST"])
def historial():
    """Ruta para el historial de ventas"""
    if request.method == "POST":
        data = request.json
        filtro = data.get("filtro", "todas")
        
        # Si es un filtro personalizado, obtener parámetros adicionales
        if filtro == "personalizado":
            fecha_inicio = data.get("fecha_inicio")
            fecha_fin = data.get("fecha_fin")
            cliente_id = data.get("cliente_id")
            ventas = obtener_ventas(filtro, fecha_inicio, fecha_fin, cliente_id)
        else:
            ventas = obtener_ventas(filtro)
        
        return jsonify({"ventas": ventas})
    
    # Para solicitudes GET, mostrar la página con todas las ventas
    ventas = obtener_ventas("todas")
    clientes = obtener_clientes()
    
    return render_template("ventas/ventas.html", ventas=ventas, clientes=clientes)

@ventas_bp.route("/detalles_venta/<int:id_venta>", methods=["GET"])
def detalles_venta(id_venta):
    """Ruta que retorna todos los detalles de la venta"""
    conexion = get_db_connection()
    cursor = conexion.cursor()

    # Obtener información de la venta
    cursor.execute("""
        SELECT v.IDVenta, v.Fecha, v.Total, COALESCE(c.NombreCompleto, 'Cliente General') as Cliente, 
               COALESCE(v.MetodoPago, 'efectivo') as MetodoPago, COALESCE(v.Descuento, 0) as Descuento
        FROM Venta v
        LEFT JOIN Cliente c ON v.IDCliente = c.IDCliente
        WHERE v.IDVenta = ?
    """, (id_venta,))
    
    venta_row = cursor.fetchone()
    
    if not venta_row:
        conexion.close()
        return jsonify({"error": "Venta no encontrada"}), 404
    
    venta = {
        "id": venta_row[0],
        "fecha": venta_row[1],
        "total": venta_row[2],
        "cliente": venta_row[3],
        "metodo_pago": venta_row[4],
        "descuento": venta_row[5]
    }

    # Obtener detalles de la venta
    cursor.execute("""
        SELECT Producto.Nombre, Detalle_Venta.Cantidad, Detalle_Venta.PrecioUnitario
        FROM Detalle_Venta
        JOIN Producto ON Detalle_Venta.IDProducto = Producto.IDProducto
        WHERE Detalle_Venta.IDVenta = ?
    """, (id_venta,))

    detalles = [
        {"nombre": row[0], "cantidad": row[1], "precio_unitario": row[2]}
        for row in cursor.fetchall()
    ]
    
    conexion.close()
    return jsonify({"venta": venta, "detalles": detalles})


#rutas para el area de reporte de ventas
@ventas_bp.route("/reporte")
@role_required(['admin', 'gerente'])
def reporte():
    db = get_db_connection()
    cursor = db.cursor()
    
    # Fecha actual para filtros predeterminados
    fecha_actual = datetime.now().strftime('%Y-%m-%d')
    
    # Agrupar ventas por fecha (solo fecha sin hora)
    cursor.execute("""
        SELECT DATE(Fecha) AS Fecha, SUM(Total) AS TotalVentas
        FROM Venta
        GROUP BY DATE(Fecha)
        ORDER BY DATE(Fecha)
    """)
    ventas = cursor.fetchall()

    # Preparar datos para gráficos
    fechas = [row["Fecha"] for row in reversed(ventas[-7:] if len(ventas) > 7 else ventas)]
    totales = [row["TotalVentas"] for row in reversed(ventas[-7:] if len(ventas) > 7 else ventas)]
    
    # Calcular crecimiento respecto al día anterior
    ventas_con_crecimiento = []
    prev_total = None
    for row in ventas:
        fecha = row["Fecha"]
        total = row["TotalVentas"]
        if prev_total is None:
            crecimiento = 0
        else:
            try:
                crecimiento = (total - prev_total)
            except ZeroDivisionError:
                crecimiento = 0
        ventas_con_crecimiento.append({
            "Fecha": fecha,
            "TotalVentas": total,
            "Crecimiento": round(crecimiento, 2)
        })
        prev_total = total

    # Gráfico: top 5 productos últimos 7 días
    cursor.execute("""
        SELECT P.Nombre, SUM(DV.Cantidad) as TotalVendido, SUM(DV.Cantidad * DV.PrecioUnitario) as TotalVentas
        FROM Detalle_Venta DV
        JOIN Producto P ON DV.IDProducto = P.IDProducto
        JOIN Venta V ON V.IDVenta = DV.IDVenta
        WHERE Fecha >= date('now', '-6 days')
        GROUP BY P.IDProducto
        ORDER BY TotalVendido DESC
        LIMIT 5
    """)
    top_productos = cursor.fetchall()
    
    nombres_productos = [p["Nombre"] for p in top_productos]
    cantidades_vendidas = [p["TotalVendido"] for p in top_productos]
    
    # Obtener ventas recientes
    cursor.execute("""
        SELECT V.IDVenta, V.Fecha, V.Total, COALESCE(C.NombreCompleto, 'Cliente General') as Cliente
        FROM Venta V
        LEFT JOIN Cliente C ON V.IDCliente = C.IDCliente
        ORDER BY V.Fecha DESC
        LIMIT 5
    """)
    ventas_recientes = cursor.fetchall()
    
    # Calcular KPIs para el dashboard
    
    # 1. Total ventas del período (último mes por defecto)
    cursor.execute("""
        SELECT SUM(Total) as TotalVentas
        FROM Venta
        WHERE Fecha >= date('now', '-30 days')
    """)
    result = cursor.fetchone()
    total_ventas_periodo = result["TotalVentas"] if result and result["TotalVentas"] else 0
    
    # 2. Total ventas del período anterior (para comparación)
    cursor.execute("""
        SELECT SUM(Total) as TotalVentas
        FROM Venta
        WHERE Fecha >= date('now', '-60 days') AND Fecha < date('now', '-30 days')
    """)
    result = cursor.fetchone()
    total_ventas_periodo_anterior = result["TotalVentas"] if result and result["TotalVentas"] else 0
    
    # 3. Calcular porcentaje de crecimiento
    if total_ventas_periodo_anterior > 0:
        porcentaje_crecimiento_ventas = round(((total_ventas_periodo - total_ventas_periodo_anterior) / total_ventas_periodo_anterior) * 100, 2)
    else:
        porcentaje_crecimiento_ventas = 100 if total_ventas_periodo > 0 else 0
    
    # 4. Ticket promedio
    cursor.execute("""
        SELECT AVG(Total) as TicketPromedio
        FROM Venta
        WHERE Fecha >= date('now', '-30 days')
    """)
    result = cursor.fetchone()
    ticket_promedio = result["TicketPromedio"] if result and result["TicketPromedio"] else 0
    
    # 5. Ticket promedio período anterior
    cursor.execute("""
        SELECT AVG(Total) as TicketPromedio
        FROM Venta
        WHERE Fecha >= date('now', '-60 days') AND Fecha < date('now', '-30 days')
    """)
    result = cursor.fetchone()
    ticket_promedio_anterior = result["TicketPromedio"] if result and result["TicketPromedio"] else 0
    
    # 6. Calcular porcentaje de crecimiento del ticket promedio
    if ticket_promedio_anterior > 0:
        porcentaje_crecimiento_ticket = round(((ticket_promedio - ticket_promedio_anterior) / ticket_promedio_anterior) * 100, 2)
    else:
        porcentaje_crecimiento_ticket = 100 if ticket_promedio > 0 else 0
    
    # 7. Total transacciones
    cursor.execute("""
        SELECT COUNT(*) as TotalTransacciones
        FROM Venta
        WHERE Fecha >= date('now', '-30 days')
    """)
    result = cursor.fetchone()
    total_transacciones = result["TotalTransacciones"] if result else 0
    
    # 8. Total transacciones período anterior
    cursor.execute("""
        SELECT COUNT(*) as TotalTransacciones
        FROM Venta
        WHERE Fecha >= date('now', '-60 days') AND Fecha < date('now', '-30 days')
    """)
    result = cursor.fetchone()
    total_transacciones_anterior = result["TotalTransacciones"] if result else 0
    
    # 9. Calcular porcentaje de crecimiento de transacciones
    if total_transacciones_anterior > 0:
        porcentaje_crecimiento_transacciones = round(((total_transacciones - total_transacciones_anterior) / total_transacciones_anterior) * 100, 2)
    else:
        porcentaje_crecimiento_transacciones = 100 if total_transacciones > 0 else 0
    
    # 10. Total productos vendidos
    cursor.execute("""
        SELECT SUM(Cantidad) as TotalProductos
        FROM Detalle_Venta DV
        JOIN Venta V ON V.IDVenta = DV.IDVenta
        WHERE V.Fecha >= date('now', '-30 days')
    """)
    result = cursor.fetchone()
    total_productos_vendidos = result["TotalProductos"] if result and result["TotalProductos"] else 0
    
    # 11. Total productos vendidos período anterior
    cursor.execute("""
        SELECT SUM(Cantidad) as TotalProductos
        FROM Detalle_Venta DV
        JOIN Venta V ON V.IDVenta = DV.IDVenta
        WHERE V.Fecha >= date('now', '-60 days') AND V.Fecha < date('now', '-30 days')
    """)
    result = cursor.fetchone()
    total_productos_vendidos_anterior = result["TotalProductos"] if result and result["TotalProductos"] else 0
    
    # 12. Calcular porcentaje de crecimiento de productos vendidos
    if total_productos_vendidos_anterior > 0:
        porcentaje_crecimiento_productos = round(((total_productos_vendidos - total_productos_vendidos_anterior) / total_productos_vendidos_anterior) * 100, 2)
    else:
        porcentaje_crecimiento_productos = 100 if total_productos_vendidos > 0 else 0
    
    # Obtener categorías para filtros
    cursor.execute("""
        SELECT IDCategoria, Nombre
        FROM Categoria
        ORDER BY Nombre
    """)
    categorias = cursor.fetchall()
    
    # Obtener rendimiento de productos (ejemplo)
    cursor.execute("""
        SELECT 
            P.Nombre, 
            C.Nombre as Categoria,
            SUM(DV.Cantidad) as UnidadesVendidas,
            AVG(DV.PrecioUnitario) as PrecioPromedio,
            SUM(DV.Cantidad * DV.PrecioUnitario) as TotalVentas
        FROM Detalle_Venta DV
        JOIN Producto P ON DV.IDProducto = P.IDProducto
        JOIN Categoria C ON P.IDCategoria = C.IDCategoria
        JOIN Venta V ON V.IDVenta = DV.IDVenta
        WHERE V.Fecha >= date('now', '-30 days')
        GROUP BY P.IDProducto
        ORDER BY TotalVentas DESC
        LIMIT 20
    """)
    productos_rendimiento_raw = cursor.fetchall()
    
    # Calcular porcentaje del total para cada producto
    total_ventas_productos = sum(p["TotalVentas"] for p in productos_rendimiento_raw)
    productos_rendimiento = []
    
    for producto in productos_rendimiento_raw:
        porcentaje = round((producto["TotalVentas"] / total_ventas_productos * 100), 2) if total_ventas_productos > 0 else 0
        productos_rendimiento.append({
            "Nombre": producto["Nombre"],
            "Categoria": producto["Categoria"],
            "UnidadesVendidas": producto["UnidadesVendidas"],
            "PrecioPromedio": round(producto["PrecioPromedio"], 2),
            "TotalVentas": round(producto["TotalVentas"], 2),
            "PorcentajeTotal": porcentaje
        })
    
    db.close()
    
    return render_template(
        "ventas/reporte_ventas.html",
        fecha_actual=fecha_actual,
        ventas_dia=ventas_con_crecimiento,
        fechas=fechas,
        totales=totales,
        nombres_productos=nombres_productos,
        cantidades_vendidas=cantidades_vendidas,
        top_productos=top_productos,
        ventas_recientes=ventas_recientes,
        total_ventas_periodo=round(total_ventas_periodo, 2),
        porcentaje_crecimiento_ventas=porcentaje_crecimiento_ventas,
        ticket_promedio=round(ticket_promedio, 2),
        porcentaje_crecimiento_ticket=porcentaje_crecimiento_ticket,
        total_transacciones=total_transacciones,
        porcentaje_crecimiento_transacciones=porcentaje_crecimiento_transacciones,
        total_productos_vendidos=total_productos_vendidos,
        porcentaje_crecimiento_productos=porcentaje_crecimiento_productos,
        categorias=categorias,
        productos_rendimiento=productos_rendimiento
    )
