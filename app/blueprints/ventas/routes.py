from flask import Blueprint, render_template, request, flash, jsonify, session, send_file
from datetime import datetime, timedelta, date
from app.utils.db import get_db_connection
from app.utils import login_required, role_required
from app.blueprints.ventas import ventas_bp
import sqlite3
import json
import io
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from io import BytesIO
import base64
import pytz


#ruta para mostrar los productos en el apartado de venta
@ventas_bp.route('/catalogo')
@role_required(['admin', 'gerente', 'vendedor'])
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
    cliente_id = data.get("cliente_id")  # <-- Nuevo: ID de cliente existente
    cliente_nombre = data.get("cliente_nombre")
    cliente_telefono = data.get("cliente_telefono")
    cambio = data.get("cambio", 0)
    nota = data.get("nota", "")
    
    nicaragua_tz = pytz.timezone('America/Managua')
    fecha = datetime.now(nicaragua_tz).strftime("%Y-%m-%d %H:%M:%S")

    user_id = session.get("user_id")

    try:
        db = get_db_connection()
        cursor = db.cursor()

        # Obtener el IDEmpleado desde el usuario en sesión
        cursor.execute("SELECT IDEmpleado FROM usuarios WHERE id = ?", (user_id,))
        empleado = cursor.fetchone()
        if not empleado:
            return jsonify({"error": "No se encontró el empleado asociado al usuario"}), 400
        id_empleado = empleado["IDEmpleado"]

        id_sucursal = 1  # Asume sucursal 1 por defecto

        # Determinar el cliente a usar
        if cliente_id:  # Cliente existente
            cliente_id_final = cliente_id
        elif cliente_nombre and cliente_telefono:  # Nuevo cliente
            cursor.execute("""
                INSERT INTO Cliente (NombreCompleto, Telefono) VALUES (?, ?)
            """, (cliente_nombre, cliente_telefono))
            cliente_id_final = cursor.lastrowid
        else:  # Sin cliente (venta general)
            cliente_id_final = None

        # Insertar la venta
        cursor.execute("""
            INSERT INTO Venta (Fecha, Total, IDEmpleado, IDCliente, IDSucursal, MetodoPago, Descuento)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (fecha, total, id_empleado, cliente_id_final, id_sucursal, tipo_pago, descuento))
        venta_id = cursor.lastrowid

        # Insertar los productos vendidos y actualizar stock
        for producto in productos:
            id_producto = producto["id"]
            cantidad = producto["cantidad"]
            precio = producto["precio"]
            subtotal = cantidad * precio

            cursor.execute("""
                INSERT INTO Detalle_Venta (IDVenta, IDProducto, Cantidad, PrecioUnitario, Subtotal)
                VALUES (?, ?, ?, ?, ?)
            """, (venta_id, id_producto, cantidad, precio, subtotal))

            cursor.execute("""
                UPDATE Stock_Sucursal SET Cantidad = Cantidad - ?
                WHERE IDProducto = ? AND IDSucursal = ?
            """, (cantidad, id_producto, id_sucursal))

        db.commit()
        return jsonify({"success": True, "mensaje": "Venta guardada exitosamente"}), 200

    except Exception as e:
        print("Error:", e)
        db.rollback()
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
@role_required(['admin', 'gerente', 'vendedor'])
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

    # Obtener información de la venta, incluyendo el empleado
    cursor.execute("""
        SELECT v.IDVenta, v.Fecha, v.Total, 
               COALESCE(c.NombreCompleto, 'Cliente General') as Cliente, 
               COALESCE(v.MetodoPago, 'efectivo') as MetodoPago, 
               COALESCE(v.Descuento, 0) as Descuento,
               COALESCE(e.NombreCompleto, 'No registrado') as Empleado
        FROM Venta v
        LEFT JOIN Cliente c ON v.IDCliente = c.IDCliente
        LEFT JOIN Empleado e ON v.IDEmpleado = e.IDEmpleado
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
        "descuento": venta_row[5],
        "empleado": venta_row[6]
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


#ruta para la busqueda de clientes en la vista de finalizar venta

@ventas_bp.route('/buscar-clientes', methods=['POST'])
def buscar_clientes():
    try:
        termino = request.json.get('termino', '').strip()
        
        if len(termino) < 2:
            return jsonify({'error': 'Ingrese al menos 2 caracteres para buscar'}), 400
        
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row  # <-- Asegura que fetchall devuelve dict-like rows
        cursor = conn.cursor()
        
        query = """
        SELECT IDCliente, NombreCompleto, Telefono, Email 
        FROM Cliente 
        WHERE NombreCompleto LIKE ? OR Telefono LIKE ?
        LIMIT 10
        """
        
        search_term = f'%{termino}%'
        cursor.execute(query, (search_term, search_term))
        clientes = cursor.fetchall()
        
        resultados = [dict(cliente) for cliente in clientes]
        
        conn.close()
        
        return jsonify({'clientes': resultados})
        
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        return jsonify({'error': str(e)}), 500


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


#ruta para el dashboard de ventas
@ventas_bp.route("/dashboard_datos", methods=["POST"])
@role_required(['admin', 'gerente'])
def dashboard_datos():
    data = request.get_json()
    fecha_inicio = data.get("fecha_inicio")
    fecha_fin = data.get("fecha_fin")

    db = get_db_connection()
    cursor = db.cursor()

    # Ventas por día para el rango seleccionado
    cursor.execute("""
        SELECT DATE(Fecha) AS Fecha, SUM(Total) AS TotalVentas
        FROM Venta
        WHERE DATE(Fecha) BETWEEN ? AND ?
        GROUP BY DATE(Fecha)
        ORDER BY DATE(Fecha)
    """, (fecha_inicio, fecha_fin))
    ventas = cursor.fetchall()
    fechas = [row["Fecha"] for row in ventas]
    totales = [row["TotalVentas"] for row in ventas]

    # KPIs
    cursor.execute("""
        SELECT SUM(Total) as TotalVentas, COUNT(*) as TotalTransacciones, AVG(Total) as TicketPromedio
        FROM Venta
        WHERE DATE(Fecha) BETWEEN ? AND ?
    """, (fecha_inicio, fecha_fin))
    kpi = cursor.fetchone()
    total_ventas = kpi["TotalVentas"] or 0
    total_transacciones = kpi["TotalTransacciones"] or 0
    ticket_promedio = kpi["TicketPromedio"] or 0

    # Top productos
    cursor.execute("""
        SELECT P.Nombre, SUM(DV.Cantidad) as TotalVendido, SUM(DV.Cantidad * DV.PrecioUnitario) as TotalVentas
        FROM Detalle_Venta DV
        JOIN Producto P ON DV.IDProducto = P.IDProducto
        JOIN Venta V ON V.IDVenta = DV.IDVenta
        WHERE DATE(V.Fecha) BETWEEN ? AND ?
        GROUP BY P.IDProducto
        ORDER BY TotalVendido DESC
        LIMIT 5
    """, (fecha_inicio, fecha_fin))
    top_productos = cursor.fetchall()
    nombres_productos = [p["Nombre"] for p in top_productos]
    cantidades_vendidas = [p["TotalVendido"] for p in top_productos]

    db.close()

    return jsonify({
        "fechas": fechas,
        "totales": totales,
        "total_ventas": round(total_ventas, 2),
        "total_transacciones": total_transacciones,
        "ticket_promedio": round(ticket_promedio, 2),
        "nombres_productos": nombres_productos,
        "cantidades_vendidas": cantidades_vendidas
    })

@ventas_bp.route("/filtrar_productos", methods=["POST"])
@role_required(['admin', 'gerente'])
def filtrar_productos():
    data = request.get_json()
    fecha_inicio = data.get("fecha_inicio")
    fecha_fin = data.get("fecha_fin")
    id_categoria = data.get("id_categoria")

    db = get_db_connection()
    cursor = db.cursor()

    # Construir la consulta SQL con los filtros
    query = """
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
        WHERE DATE(V.Fecha) BETWEEN ? AND ?
    """
    
    params = [fecha_inicio, fecha_fin]
    
    # Agregar filtro de categoría si se seleccionó una
    if id_categoria:
        query += " AND P.IDCategoria = ?"
        params.append(id_categoria)
    
    query += """
        GROUP BY P.IDProducto
        ORDER BY TotalVentas DESC
        LIMIT 20
    """
    
    cursor.execute(query, params)
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
    
    return jsonify({
        "productos": productos_rendimiento
    })

#backend para la seccion de balance general 

@ventas_bp.route('/balance')
def balance():
    """Página principal del balance general"""
    conn = get_db_connection()
    
    # Obtener categorías para el filtro
    categorias = conn.execute('SELECT IDCategoria, Nombre FROM Categoria ORDER BY Nombre').fetchall()
    
    # Obtener sucursales para el filtro
    sucursales = conn.execute('SELECT IDSucursal, Nombre FROM Sucursal ORDER BY Nombre').fetchall()
    
    conn.close()
    
    return render_template('reportes/balance.html', 
                         categorias=categorias, 
                         sucursales=sucursales)

@ventas_bp.route('/balance/data', methods=['POST'])
def balance_data():
    """Obtener datos para el dashboard"""
    try:
        filters = request.json or {}
        
        # Obtener KPIs
        kpis = get_kpis(filters)
        
        # Obtener top productos
        top_products = get_top_products(filters)
        
        # Obtener transacciones
        transactions = get_transactions(filters)
        
        return jsonify({
            'kpis': kpis,
            'top_products': top_products,
            'transactions': transactions
        })
        
    except Exception as e:
        print(f"Error en balance_data: {e}")
        return jsonify({'error': str(e)}), 500

@ventas_bp.route('/balance/chart', methods=['POST'])
def balance_chart():
    """Obtener datos para el gráfico de ingresos vs egresos"""
    try:
        data = request.json or {}
        filters = {k: v for k, v in data.items() if k != 'period'}
        period = data.get('period', 'monthly')
        
        chart_data = get_income_expense_chart_data(filters, period)
        
        return jsonify(chart_data)
        
    except Exception as e:
        print(f"Error en balance_chart: {e}")
        return jsonify({'error': str(e)}), 500

@ventas_bp.route('/balance/transactions', methods=['POST'])
def balance_transactions():
    """Obtener transacciones agrupadas"""
    try:
        data = request.json or {}
        filters = {k: v for k, v in data.items() if k != 'group_by'}
        group_by = data.get('group_by', 'daily')
        
        transactions = get_grouped_transactions(filters, group_by)
        
        return jsonify({
            'transactions': transactions
        })
        
    except Exception as e:
        print(f"Error en balance_transactions: {e}")
        return jsonify({'error': str(e)}), 500

@ventas_bp.route('/balance/export/pdf', methods=['POST'])
def export_pdf():
    """Exportar reporte a PDF"""
    try:
        filters = request.json or {}
        
        # Generar PDF
        buffer = generate_pdf_report(filters)
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f'balance_general_{date.today().strftime("%Y%m%d")}.pdf',
            mimetype='application/pdf'
        )
        
    except Exception as e:
        print(f"Error en export_pdf: {e}")
        return jsonify({'error': str(e)}), 500

@ventas_bp.route('/balance/export/excel', methods=['POST'])
def export_excel():
    """Exportar reporte a Excel"""
    try:
        filters = request.json or {}
        
        # Generar Excel
        buffer = generate_excel_report(filters)
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f'balance_general_{date.today().strftime("%Y%m%d")}.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        print(f"Error en export_excel: {e}")
        return jsonify({'error': str(e)}), 500

@ventas_bp.route('/balance/note', methods=['POST'])
def save_note():
    """Guardar nota personalizada"""
    try:
        data = request.json
        title = data.get('title')
        content = data.get('content')
        filters = data.get('filters', {})
        
        conn = get_db_connection()
        
        # Crear tabla de notas si no existe
        conn.execute('''
            CREATE TABLE IF NOT EXISTS report_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                filters TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER
            )
        ''')
        
        # Insertar nota
        conn.execute('''
            INSERT INTO report_notes (title, content, filters)
            VALUES (?, ?, ?)
        ''', (title, content, json.dumps(filters)))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Error en save_note: {e}")
        return jsonify({'error': str(e)}), 500

def get_kpis(filters):
    """Calcular KPIs del negocio"""
    conn = get_db_connection()
    
    # Construir condiciones WHERE
    where_conditions = []
    params = []
    
    if filters.get('fecha_inicio'):
        where_conditions.append('DATE(fecha) >= ?')
        params.append(filters['fecha_inicio'])
    
    if filters.get('fecha_fin'):
        where_conditions.append('DATE(fecha) <= ?')
        params.append(filters['fecha_fin'])
    
    where_clause = 'WHERE ' + ' AND '.join(where_conditions) if where_conditions else ''
    
    # Ventas totales
    query_ventas = f'''
        SELECT COALESCE(SUM(Total), 0) as total_sales
        FROM Venta v
        {where_clause}
    '''
    
    total_sales = conn.execute(query_ventas, params).fetchone()['total_sales']
    
    # Compras totales
    query_compras = f'''
        SELECT COALESCE(SUM(Total), 0) as total_purchases
        FROM Compra c
        {where_clause.replace('v.', 'c.')}
    '''
    
    total_purchases = conn.execute(query_compras, params).fetchone()['total_purchases']
    
    # Ganancia neta
    net_profit = total_sales - total_purchases
    
    # Margen de utilidad
    profit_margin = (net_profit / total_sales * 100) if total_sales > 0 else 0
    
    # Calcular crecimiento vs período anterior
    sales_growth = calculate_growth('Venta', 'Total', filters)
    purchases_growth = calculate_growth('Compra', 'Total', filters)
    profit_growth = sales_growth - purchases_growth
    
    # Calcular crecimiento del margen
    previous_margin = get_previous_period_margin(filters)
    margin_growth = profit_margin - previous_margin
    
    conn.close()
    
    return {
        'total_sales': float(total_sales),
        'total_purchases': float(total_purchases),
        'net_profit': float(net_profit),
        'profit_margin': float(profit_margin),
        'sales_growth': float(sales_growth),
        'purchases_growth': float(purchases_growth),
        'profit_growth': float(profit_growth),
        'margin_growth': float(margin_growth)
    }

def get_top_products(filters):
    """Obtener top 5 productos más vendidos"""
    conn = get_db_connection()
    
    # Construir condiciones WHERE
    where_conditions = []
    params = []
    
    if filters.get('fecha_inicio'):
        where_conditions.append('DATE(v.Fecha) >= ?')
        params.append(filters['fecha_inicio'])
    
    if filters.get('fecha_fin'):
        where_conditions.append('DATE(v.Fecha) <= ?')
        params.append(filters['fecha_fin'])
    
    if filters.get('categoria'):
        where_conditions.append('p.IDCategoria = ?')
        params.append(filters['categoria'])
    
    if filters.get('sucursal'):
        where_conditions.append('v.IDSucursal = ?')
        params.append(filters['sucursal'])
    
    where_clause = 'WHERE ' + ' AND '.join(where_conditions) if where_conditions else ''
    
    query = f'''
        SELECT 
            p.Nombre as name,
            c.Nombre as category,
            SUM(dv.Cantidad) as quantity_sold,
            SUM(dv.Subtotal) as total_sales
        FROM Detalle_Venta dv
        JOIN Producto p ON dv.IDProducto = p.IDProducto
        JOIN Categoria c ON p.IDCategoria = c.IDCategoria
        JOIN Venta v ON dv.IDVenta = v.IDVenta
        {where_clause}
        GROUP BY p.IDProducto, p.Nombre, c.Nombre
        ORDER BY total_sales DESC
        LIMIT 5
    '''
    
    results = conn.execute(query, params).fetchall()
    conn.close()
    
    return [dict(row) for row in results]

def get_transactions(filters):
    """Obtener transacciones detalladas"""
    conn = get_db_connection()
    
    transactions = []
    
    # Construir condiciones WHERE
    where_conditions = []
    params = []
    
    if filters.get('fecha_inicio'):
        where_conditions.append('DATE(fecha) >= ?')
        params.append(filters['fecha_inicio'])
    
    if filters.get('fecha_fin'):
        where_conditions.append('DATE(fecha) <= ?')
        params.append(filters['fecha_fin'])
    
    where_clause = 'WHERE ' + ' AND '.join(where_conditions) if where_conditions else ''
    
    # Obtener ventas
    query_ventas = f'''
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
    
    ventas = conn.execute(query_ventas, params).fetchall()
    transactions.extend([dict(row) for row in ventas])
    
    # Obtener compras
    query_compras = f'''
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
    
    compras = conn.execute(query_compras, params).fetchall()
    transactions.extend([dict(row) for row in compras])
    
    # Ordenar por fecha
    transactions.sort(key=lambda x: x['date'], reverse=True)
    
    # Calcular balance acumulado
    running_balance = 0
    for transaction in reversed(transactions):
        running_balance += transaction['balance']
        transaction['balance'] = running_balance
    
    transactions.reverse()
    
    conn.close()
    
    return transactions

def get_income_expense_chart_data(filters, period):
    """Obtener datos para el gráfico de ingresos vs egresos"""
    conn = get_db_connection()
    
    # Determinar formato de fecha según el período
    if period == 'monthly':
        date_format = '%Y-%m'
        date_trunc = "strftime('%Y-%m', fecha)"
    elif period == 'quarterly':
        date_format = '%Y-Q'
        date_trunc = "strftime('%Y', fecha) || '-Q' || ((CAST(strftime('%m', fecha) AS INTEGER) - 1) / 3 + 1)"
    else:  # yearly
        date_format = '%Y'
        date_trunc = "strftime('%Y', fecha)"
    
    # Construir condiciones WHERE
    where_conditions = []
    params = []
    
    if filters.get('fecha_inicio'):
        where_conditions.append('DATE(fecha) >= ?')
        params.append(filters['fecha_inicio'])
    
    if filters.get('fecha_fin'):
        where_conditions.append('DATE(fecha) <= ?')
        params.append(filters['fecha_fin'])
    
    where_clause = 'WHERE ' + ' AND '.join(where_conditions) if where_conditions else ''
    
    # Obtener ingresos por período
    query_ingresos = f'''
        SELECT 
            {date_trunc} as period,
            SUM(Total) as total
        FROM Venta
        {where_clause.replace('fecha', 'Fecha')}
        GROUP BY {date_trunc}
        ORDER BY period
    '''
    
    ingresos = conn.execute(query_ingresos, params).fetchall()
    
    # Obtener egresos por período
    query_egresos = f'''
        SELECT 
            {date_trunc} as period,
            SUM(Total) as total
        FROM Compra
        {where_clause.replace('fecha', 'Fecha')}
        GROUP BY {date_trunc}
        ORDER BY period
    '''
    
    egresos = conn.execute(query_egresos, params).fetchall()
    
    conn.close()
    
    # Combinar datos
    periods = set()
    income_dict = {}
    expense_dict = {}
    
    for row in ingresos:
        periods.add(row['period'])
        income_dict[row['period']] = float(row['total'])
    
    for row in egresos:
        periods.add(row['period'])
        expense_dict[row['period']] = float(row['total'])
    
    # Ordenar períodos
    sorted_periods = sorted(list(periods))
    
    # Preparar datos para el gráfico
    labels = sorted_periods
    income = [income_dict.get(period, 0) for period in sorted_periods]
    expenses = [expense_dict.get(period, 0) for period in sorted_periods]
    
    return {
        'labels': labels,
        'income': income,
        'expenses': expenses
    }

def calculate_growth(table, column, filters):
    """Calcular crecimiento vs período anterior"""
    conn = get_db_connection()
    
    # Obtener fechas del período actual
    fecha_inicio = filters.get('fecha_inicio')
    fecha_fin = filters.get('fecha_fin')
    
    if not fecha_inicio or not fecha_fin:
        return 0
    
    # Calcular duración del período
    start_date = datetime.strptime(fecha_inicio, '%Y-%m-%d')
    end_date = datetime.strptime(fecha_fin, '%Y-%m-%d')
    duration = (end_date - start_date).days
    
    # Calcular fechas del período anterior
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=duration)
    
    # Obtener total del período actual
    query_current = f'''
        SELECT COALESCE(SUM({column}), 0) as total
        FROM {table}
        WHERE DATE(Fecha) BETWEEN ? AND ?
    '''
    
    current_total = conn.execute(query_current, [fecha_inicio, fecha_fin]).fetchone()['total']
    
    # Obtener total del período anterior
    prev_total = conn.execute(query_current, [
        prev_start.strftime('%Y-%m-%d'),
        prev_end.strftime('%Y-%m-%d')
    ]).fetchone()['total']
    
    conn.close()
    
    # Calcular crecimiento porcentual
    if prev_total > 0:
        growth = ((current_total - prev_total) / prev_total) * 100
    else:
        growth = 100 if current_total > 0 else 0
    
    return growth

def get_previous_period_margin(filters):
    """Obtener margen del período anterior"""
    # Implementación similar a calculate_growth pero para margen
    return 0  # Placeholder

def generate_pdf_report(filters):
    """Generar reporte en PDF mejorado"""
    buffer = BytesIO()
    
    # Crear documento PDF
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20, bottomMargin=20)
    styles = getSampleStyleSheet()
    story = []
    
    # Estilos personalizados siguiendo el patrón de referencia
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        spaceAfter=20,
        alignment=1,  # Center
        textColor=colors.HexColor('#4361ee')
    )
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=15,
        textColor=colors.HexColor('#4361ee')
    )
    
    # Información de la empresa
    story.append(Paragraph("LIBRERÍA INDIANA", title_style))
    story.append(Spacer(1, 10))
    
    company_info = """
    <b>Dirección:</b> Vanegas, Esquipulas<br/>
    Del colegio Pablo Antonio Cuadras 500 mts al oeste<br/>
    <b>Teléfono:</b> (505) 7756-5332<br/>
    <b>Email:</b> indianaflores2@gmail.com
    """
    story.append(Paragraph(company_info, styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Título del reporte
    story.append(Paragraph("BALANCE GENERAL DEL NEGOCIO", title_style))
    story.append(Spacer(1, 10))
    
    # Información de filtros aplicados
    filter_info = "<b>Filtros Aplicados:</b><br/>"
    if filters.get('fecha_inicio') and filters.get('fecha_fin'):
        filter_info += f"Período: {filters['fecha_inicio']} al {filters['fecha_fin']}<br/>"
    if filters.get('categoria'):
        conn = get_db_connection()
        categoria_nombre = conn.execute('SELECT Nombre FROM Categoria WHERE IDCategoria = ?', 
                                      [filters['categoria']]).fetchone()
        if categoria_nombre:
            filter_info += f"Categoría: {categoria_nombre['Nombre']}<br/>"
        conn.close()
    if filters.get('sucursal'):
        conn = get_db_connection()
        sucursal_nombre = conn.execute('SELECT Nombre FROM Sucursal WHERE IDSucursal = ?', 
                                     [filters['sucursal']]).fetchone()
        if sucursal_nombre:
            filter_info += f"Sucursal: {sucursal_nombre['Nombre']}<br/>"
        conn.close()
    
    if filter_info == "<b>Filtros Aplicados:</b><br/>":
        filter_info += "Ningún filtro aplicado - Mostrando todos los datos"
    
    story.append(Paragraph(filter_info, styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Obtener datos
    kpis = get_kpis(filters)
    top_products = get_top_products(filters)
    grouped_transactions = get_grouped_transactions(filters, 'daily')
    
    # KPIs con colores
    story.append(Paragraph("INDICADORES CLAVE DE RENDIMIENTO", subtitle_style))
    
    kpi_data = [
        ['Indicador', 'Valor', 'Estado'],
        ['Ventas Totales', f"C$ {kpis['total_sales']:,.2f}", 
         '✓ Positivo' if kpis['sales_growth'] >= 0 else '⚠ Negativo'],
        ['Compras Totales', f"C$ {kpis['total_purchases']:,.2f}", 
         '✓ Controlado' if kpis['purchases_growth'] <= 10 else '⚠ Alto'],
        ['Ganancia Neta', f"C$ {kpis['net_profit']:,.2f}", 
         '✓ Rentable' if kpis['net_profit'] > 0 else '⚠ Pérdida'],
        ['Margen de Utilidad', f"{kpis['profit_margin']:.1f}%", 
         '✓ Saludable' if kpis['profit_margin'] > 15 else '⚠ Bajo']
    ]
    
    kpi_table = Table(kpi_data, colWidths=[6*inch/3, 6*inch/3, 6*inch/3])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4361ee')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(kpi_table)
    story.append(Spacer(1, 20))
    
    # Top productos
    story.append(Paragraph("TOP 5 PRODUCTOS MÁS VENDIDOS", subtitle_style))
    
    if top_products:
        product_data = [['#', 'Producto', 'Categoría', 'Cantidad', 'Ventas Totales']]
        for i, product in enumerate(top_products, 1):
            product_data.append([
                str(i),
                product['name'],
                product['category'],
                str(int(product['quantity_sold'])),
                f"C$ {product['total_sales']:,.2f}"
            ])
        
        product_table = Table(product_data)
        product_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1cc88a')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(product_table)
    else:
        story.append(Paragraph("No hay datos de productos disponibles.", styles['Normal']))
    
    story.append(Spacer(1, 20))
    
    # Reporte detallado de transacciones
    story.append(Paragraph("REPORTE DETALLADO DE TRANSACCIONES DIARIAS", subtitle_style))
    
    if grouped_transactions:
        trans_data = [['Fecha', 'Ingresos', 'Egresos', 'Balance', 'Tendencia']]
        for trans in grouped_transactions[:20]:  # Limitar a 20 registros para el PDF
            trend = 'Positivo' if trans['balance'] > 0 else 'Negativo' if trans['balance'] < 0 else 'Neutral'
            trans_data.append([
                trans['period'],
                f"C$ {trans['income']:,.2f}",
                f"C$ {trans['expense']:,.2f}",
                f"C$ {trans['balance']:,.2f}",
                trend
            ])
        
        trans_table = Table(trans_data)
        trans_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f6c23e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ALIGN', (1, 1), (-2, -1), 'RIGHT'),  # Alinear números a la derecha
        ]))
        
        story.append(trans_table)
    else:
        story.append(Paragraph("No hay transacciones disponibles.", styles['Normal']))
    
    # Pie de página
    story.append(Spacer(1, 30))
    footer_text = f"Reporte generado el {datetime.now().strftime('%d/%m/%Y a las %H:%M')}"
    story.append(Paragraph(footer_text, styles['Normal']))
    
    # Construir PDF
    doc.build(story)
    buffer.seek(0)
    
    return buffer

def generate_excel_report(filters):
    """Generar reporte en Excel"""
    buffer = BytesIO()
    
    # Obtener datos
    kpis = get_kpis(filters)
    top_products = get_top_products(filters)
    transactions = get_transactions(filters)
    
    # Crear archivo Excel con múltiples hojas
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        # Hoja de KPIs
        kpi_df = pd.DataFrame([
            ['Ventas Totales', f"C$ {kpis['total_sales']:,.2f}"],
            ['Compras Totales', f"C$ {kpis['total_purchases']:,.2f}"],
            ['Ganancia Neta', f"C$ {kpis['net_profit']:,.2f}"],
            ['Margen de Utilidad', f"{kpis['profit_margin']:.1f}%"]
        ], columns=['Indicador', 'Valor'])
        
        kpi_df.to_excel(writer, sheet_name='KPIs', index=False)
        
        # Hoja de top productos
        if top_products:
            products_df = pd.DataFrame(top_products)
            products_df.to_excel(writer, sheet_name='Top Productos', index=False)
        
        # Hoja de transacciones
        if transactions:
            transactions_df = pd.DataFrame(transactions)
            transactions_df.to_excel(writer, sheet_name='Transacciones', index=False)
    
    buffer.seek(0)
    return buffer

def get_grouped_transactions(filters, group_by='daily'):
    """Obtener transacciones agrupadas por período"""
    conn = get_db_connection()
    
    # Determinar formato de agrupación
    if group_by == 'weekly':
        date_format = "strftime('%Y-W%W', fecha)"
        date_label = "Semana"
    elif group_by == 'monthly':
        date_format = "strftime('%Y-%m', fecha)"
        date_label = "Mes"
    else:  # daily
        date_format = "DATE(fecha)"
        date_label = "Día"
    
    # Construir condiciones WHERE
    where_conditions = []
    params = []
    
    if filters.get('fecha_inicio'):
        where_conditions.append('DATE(fecha) >= ?')
        params.append(filters['fecha_inicio'])
    
    if filters.get('fecha_fin'):
        where_conditions.append('DATE(fecha) <= ?')
        params.append(filters['fecha_fin'])
    
    where_clause = 'WHERE ' + ' AND '.join(where_conditions) if where_conditions else ''
    
    # Obtener ingresos agrupados
    query_ingresos = f'''
        SELECT 
            {date_format} as period,
            SUM(Total) as total
        FROM Venta
        {where_clause.replace('fecha', 'Fecha')}
        GROUP BY {date_format}
        ORDER BY period
    '''
    
    ingresos = conn.execute(query_ingresos, params).fetchall()
    
    # Obtener egresos agrupados
    query_egresos = f'''
        SELECT 
            {date_format} as period,
            SUM(Total) as total
        FROM Compra
        {where_clause.replace('fecha', 'Fecha')}
        GROUP BY {date_format}
        ORDER BY period
    '''
    
    egresos = conn.execute(query_egresos, params).fetchall()
    
    conn.close()
    
    # Combinar datos
    periods = set()
    income_dict = {}
    expense_dict = {}
    
    for row in ingresos:
        periods.add(row['period'])
        income_dict[row['period']] = float(row['total'])
    
    for row in egresos:
        periods.add(row['period'])
        expense_dict[row['period']] = float(row['total'])
    
    # Crear lista de transacciones agrupadas
    transactions = []
    for period in sorted(periods):
        income = income_dict.get(period, 0)
        expense = expense_dict.get(period, 0)
        balance = income - expense
        
        transactions.append({
            'period': period,
            'income': income,
            'expense': expense,
            'balance': balance
        })
    
    return transactions
