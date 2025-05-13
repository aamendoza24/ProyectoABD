from flask import Blueprint, render_template, request, flash, jsonify
from datetime import datetime, timedelta
from app.utils.db import get_db_connection
from app.utils import login_required
from app.blueprints.dashboard import dashboard_bp

#dashboard_bp = Blueprint('dashboard', __name__, url_prefix='')

@dashboard_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    # Obtener el período seleccionado (por defecto: semana)
    periodo = request.args.get('periodo', 'week')
    
    # Calcular fechas según el período
    hoy = datetime.now()
    fecha_fin = hoy.strftime('%Y-%m-%d 23:59:59')
    
    if periodo == 'today':
        fecha_inicio = hoy.strftime('%Y-%m-%d 00:00:00')
        periodo_anterior_inicio = (hoy - timedelta(days=1)).strftime('%Y-%m-%d 00:00:00')
        periodo_anterior_fin = (hoy - timedelta(days=1)).strftime('%Y-%m-%d 23:59:59')
    elif periodo == 'yesterday':
        fecha_inicio = (hoy - timedelta(days=1)).strftime('%Y-%m-%d 00:00:00')
        fecha_fin = (hoy - timedelta(days=1)).strftime('%Y-%m-%d 23:59:59')
        periodo_anterior_inicio = (hoy - timedelta(days=2)).strftime('%Y-%m-%d 00:00:00')
        periodo_anterior_fin = (hoy - timedelta(days=2)).strftime('%Y-%m-%d 23:59:59')
    elif periodo == 'week':
        fecha_inicio = (hoy - timedelta(days=hoy.weekday())).strftime('%Y-%m-%d 00:00:00')
        periodo_anterior_inicio = (hoy - timedelta(days=hoy.weekday() + 7)).strftime('%Y-%m-%d 00:00:00')
        periodo_anterior_fin = (hoy - timedelta(days=hoy.weekday() + 1)).strftime('%Y-%m-%d 23:59:59')
    elif periodo == 'month':
        fecha_inicio = hoy.replace(day=1).strftime('%Y-%m-%d 00:00:00')
        mes_anterior = hoy.month - 1 if hoy.month > 1 else 12
        año_anterior = hoy.year if hoy.month > 1 else hoy.year - 1
        periodo_anterior_inicio = hoy.replace(year=año_anterior, month=mes_anterior, day=1).strftime('%Y-%m-%d 00:00:00')
        if mes_anterior == 12:
            periodo_anterior_fin = hoy.replace(year=año_anterior, month=mes_anterior, day=31).strftime('%Y-%m-%d 23:59:59')
        else:
            periodo_anterior_fin = hoy.replace(year=año_anterior, month=mes_anterior + 1, day=1) - timedelta(days=1)
            periodo_anterior_fin = periodo_anterior_fin.strftime('%Y-%m-%d 23:59:59')
    elif periodo == 'year':
        fecha_inicio = hoy.replace(month=1, day=1).strftime('%Y-%m-%d 00:00:00')
        periodo_anterior_inicio = hoy.replace(year=hoy.year - 1, month=1, day=1).strftime('%Y-%m-%d 00:00:00')
        periodo_anterior_fin = hoy.replace(year=hoy.year - 1, month=12, day=31).strftime('%Y-%m-%d 23:59:59')
    
    # Conectar a la base de datos
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Obtener productos con bajo stock
    cursor.execute("""
        SELECT p.IDProducto, p.Nombre, p.Precio, c.Nombre as Categoria, s.Cantidad as Stock
        FROM Producto AS p
        JOIN Categoria AS c ON p.IDCategoria = c.IDCategoria
        JOIN Stock_Sucursal AS s ON p.IDProducto = s.IDProducto
        WHERE s.Cantidad < 10
        ORDER BY s.Cantidad ASC
        LIMIT 5
    """)
    productos_bajo_stock = cursor.fetchall()
    
    # Mostrar alerta de bajo stock
    productos_alerta = []
    for producto in productos_bajo_stock:
        if producto['Stock'] < 5:
            productos_alerta.append(f"{producto['Nombre']} ({producto['Stock']} unidades)")
    
    if productos_alerta:
        mensaje = "⚠️ Los siguientes productos tienen stock crítico:\n" + ", ".join(productos_alerta)
        flash(mensaje, "warning")
    
    # 2. Obtener KPIs del período actual
    
    # Total de ventas
    cursor.execute("""
        SELECT SUM(Total) as TotalVentas
        FROM Venta
        WHERE Fecha BETWEEN ? AND ?
    """, (fecha_inicio, fecha_fin))
    result = cursor.fetchone()
    total_ventas = result['TotalVentas'] if result and result['TotalVentas'] else 0
    
    # Total de ventas del período anterior
    cursor.execute("""
        SELECT SUM(Total) as TotalVentas
        FROM Venta
        WHERE Fecha BETWEEN ? AND ?
    """, (periodo_anterior_inicio, periodo_anterior_fin))
    result = cursor.fetchone()
    total_ventas_anterior = result['TotalVentas'] if result and result['TotalVentas'] else 0
    
    # Calcular porcentaje de crecimiento
    if total_ventas_anterior > 0:
        porcentaje_ventas = round(((total_ventas - total_ventas_anterior) / total_ventas_anterior) * 100, 2)
    else:
        porcentaje_ventas = 100 if total_ventas > 0 else 0
    
    # Total de transacciones
    cursor.execute("""
        SELECT COUNT(*) as TotalTransacciones
        FROM Venta
        WHERE Fecha BETWEEN ? AND ?
    """, (fecha_inicio, fecha_fin))
    result = cursor.fetchone()
    total_transacciones = result['TotalTransacciones'] if result else 0
    
    # Total de transacciones del período anterior
    cursor.execute("""
        SELECT COUNT(*) as TotalTransacciones
        FROM Venta
        WHERE Fecha BETWEEN ? AND ?
    """, (periodo_anterior_inicio, periodo_anterior_fin))
    result = cursor.fetchone()
    total_transacciones_anterior = result['TotalTransacciones'] if result else 0
    
    # Calcular porcentaje de crecimiento de transacciones
    if total_transacciones_anterior > 0:
        porcentaje_transacciones = round(((total_transacciones - total_transacciones_anterior) / total_transacciones_anterior) * 100, 2)
    else:
        porcentaje_transacciones = 100 if total_transacciones > 0 else 0
    
    # Ticket promedio
    ticket_promedio = round(total_ventas / total_transacciones, 2) if total_transacciones > 0 else 0
    ticket_promedio_anterior = round(total_ventas_anterior / total_transacciones_anterior, 2) if total_transacciones_anterior > 0 else 0
    
    # Calcular porcentaje de crecimiento del ticket promedio
    if ticket_promedio_anterior > 0:
        porcentaje_ticket = round(((ticket_promedio - ticket_promedio_anterior) / ticket_promedio_anterior) * 100, 2)
    else:
        porcentaje_ticket = 100 if ticket_promedio > 0 else 0
    
    # Total productos vendidos
    cursor.execute("""
        SELECT SUM(Cantidad) as TotalProductos
        FROM Detalle_Venta DV
        JOIN Venta V ON V.IDVenta = DV.IDVenta
        WHERE V.Fecha BETWEEN ? AND ?
    """, (fecha_inicio, fecha_fin))
    result = cursor.fetchone()
    productos_vendidos = result['TotalProductos'] if result and result['TotalProductos'] else 0
    
    # Total productos vendidos período anterior
    cursor.execute("""
        SELECT SUM(Cantidad) as TotalProductos
        FROM Detalle_Venta DV
        JOIN Venta V ON V.IDVenta = DV.IDVenta
        WHERE V.Fecha BETWEEN ? AND ?
    """, (periodo_anterior_inicio, periodo_anterior_fin))
    result = cursor.fetchone()
    productos_vendidos_anterior = result['TotalProductos'] if result and result['TotalProductos'] else 0
    
    # Calcular porcentaje de crecimiento de productos vendidos
    if productos_vendidos_anterior > 0:
        porcentaje_productos = round(((productos_vendidos - productos_vendidos_anterior) / productos_vendidos_anterior) * 100, 2)
    else:
        porcentaje_productos = 100 if productos_vendidos > 0 else 0
    
    # 3. Obtener datos para el gráfico de ventas
    # Determinar el intervalo según el período
    if periodo in ['today', 'yesterday']:
        # Para hoy o ayer, mostrar ventas por hora
        cursor.execute("""
            SELECT strftime('%H:00', Fecha) as Hora, SUM(Total) as Total
            FROM Venta
            WHERE Fecha BETWEEN ? AND ?
            GROUP BY strftime('%H', Fecha)
            ORDER BY Hora
        """, (fecha_inicio, fecha_fin))
        ventas_por_periodo = cursor.fetchall()
        fechas = [row['Hora'] for row in ventas_por_periodo]
        ventas_diarias = [float(row['Total']) for row in ventas_por_periodo]
    elif periodo == 'week':
        # Para la semana, mostrar ventas por día
        dias = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
        cursor.execute("""
            SELECT strftime('%w', Fecha) as DiaSemana, SUM(Total) as Total
            FROM Venta
            WHERE Fecha BETWEEN ? AND ?
            GROUP BY DiaSemana
            ORDER BY DiaSemana
        """, (fecha_inicio, fecha_fin))
        ventas_por_periodo = cursor.fetchall()
        
        # Inicializar con ceros
        ventas_por_dia = [0] * 7
        
        # Llenar con datos reales
        for row in ventas_por_periodo:
            # SQLite devuelve 0 para domingo, 1-6 para lunes-sábado
            dia_idx = int(row['DiaSemana'])
            # Ajustar para que 0 sea lunes y 6 sea domingo
            dia_idx = 6 if dia_idx == 0 else dia_idx - 1
            ventas_por_dia[dia_idx] = float(row['Total'])
        
        fechas = dias
        ventas_diarias = ventas_por_dia
    elif periodo == 'month':
        # Para el mes, mostrar ventas por día del mes
        dias_mes = (hoy.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        dias_mes = dias_mes.day
        
        cursor.execute("""
            SELECT strftime('%d', Fecha) as Dia, SUM(Total) as Total
            FROM Venta
            WHERE Fecha BETWEEN ? AND ?
            GROUP BY Dia
            ORDER BY Dia
        """, (fecha_inicio, fecha_fin))
        ventas_por_periodo = cursor.fetchall()
        
        # Inicializar con ceros
        ventas_por_dia = [0] * dias_mes
        
        # Llenar con datos reales
        for row in ventas_por_periodo:
            dia_idx = int(row['Dia']) - 1  # Días comienzan en 1
            ventas_por_dia[dia_idx] = float(row['Total'])
        
        fechas = [str(i) for i in range(1, dias_mes + 1)]
        ventas_diarias = ventas_por_dia
    else:  # año
        # Para el año, mostrar ventas por mes
        meses = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
        
        cursor.execute("""
            SELECT strftime('%m', Fecha) as Mes, SUM(Total) as Total
            FROM Venta
            WHERE Fecha BETWEEN ? AND ?
            GROUP BY Mes
            ORDER BY Mes
        """, (fecha_inicio, fecha_fin))
        ventas_por_periodo = cursor.fetchall()
        
        # Inicializar con ceros
        ventas_por_mes = [0] * 12
        
        # Llenar con datos reales
        for row in ventas_por_periodo:
            mes_idx = int(row['Mes']) - 1  # Meses comienzan en 01
            ventas_por_mes[mes_idx] = float(row['Total'])
        
        fechas = meses
        ventas_diarias = ventas_por_mes
    
    # 4. Obtener datos para el gráfico de categorías
    cursor.execute("""
        SELECT c.Nombre, SUM(dv.Subtotal) as Total
        FROM Detalle_Venta dv
        JOIN Producto p ON dv.IDProducto = p.IDProducto
        JOIN Categoria c ON p.IDCategoria = c.IDCategoria
        JOIN Venta v ON dv.IDVenta = v.IDVenta
        WHERE v.Fecha BETWEEN ? AND ?
        GROUP BY c.IDCategoria
        ORDER BY Total DESC
    """, (fecha_inicio, fecha_fin))
    categorias_ventas = cursor.fetchall()
    
    categorias_labels = [row['Nombre'] for row in categorias_ventas]
    categorias_data = [float(row['Total']) for row in categorias_ventas]
    
    # 5. Obtener productos más vendidos
    cursor.execute("""
        SELECT p.Nombre, c.Nombre as Categoria, SUM(dv.Cantidad) as Unidades, SUM(dv.Subtotal) as Total
        FROM Detalle_Venta dv
        JOIN Producto p ON dv.IDProducto = p.IDProducto
        JOIN Categoria c ON p.IDCategoria = c.IDCategoria
        JOIN Venta v ON dv.IDVenta = v.IDVenta
        WHERE v.Fecha BETWEEN ? AND ?
        GROUP BY p.IDProducto
        ORDER BY Unidades DESC
        LIMIT 5
    """, (fecha_inicio, fecha_fin))
    productos_mas_vendidos = cursor.fetchall()
    
    # 6. Obtener ventas recientes
    cursor.execute("""
        SELECT v.IDVenta, datetime(v.Fecha) as Fecha, 
               COALESCE(c.NombreCompleto, 'Cliente General') as Cliente, 
               v.MetodoPago, v.Total
        FROM Venta v
        LEFT JOIN Cliente c ON v.IDCliente = c.IDCliente
        ORDER BY v.Fecha DESC
        LIMIT 5
    """)
    ventas_recientes = cursor.fetchall()
    
    # 7. Obtener categorías populares con iconos
    cursor.execute("""
        SELECT c.Nombre, SUM(dv.Subtotal) as Total
        FROM Detalle_Venta dv
        JOIN Producto p ON dv.IDProducto = p.IDProducto
        JOIN Categoria c ON p.IDCategoria = c.IDCategoria
        JOIN Venta v ON dv.IDVenta = v.IDVenta
        WHERE v.Fecha BETWEEN ? AND ?
        GROUP BY c.IDCategoria
        ORDER BY Total DESC
        LIMIT 5
    """, (fecha_inicio, fecha_fin))
    categorias_raw = cursor.fetchall()
    
    # Calcular porcentaje del total para cada categoría
    total_categorias = sum(float(cat['Total']) for cat in categorias_raw)
    
    # Asignar iconos y colores según el nombre de la categoría
    iconos_categorias = {
        'Libros': {'Icono': 'mdi-book-open-page-variant', 'Color': 'books'},
        'Útiles Escolares': {'Icono': 'mdi-pencil', 'Color': 'school'},
        'Papelería': {'Icono': 'mdi-file-document', 'Color': 'office'},
        'Arte': {'Icono': 'mdi-palette', 'Color': 'art'},
        'Oficina': {'Icono': 'mdi-briefcase', 'Color': 'tech'}
    }
    
    categorias_populares = []
    for categoria in categorias_raw:
        nombre = categoria['Nombre']
        total = float(categoria['Total'])
        porcentaje = round((total / total_categorias * 100), 2) if total_categorias > 0 else 0
        
        # Asignar icono y color predeterminados si no está en el diccionario
        icono_info = iconos_categorias.get(nombre, {'Icono': 'mdi-tag', 'Color': 'primary'})
        
        categorias_populares.append({
            'Nombre': nombre,
            'Total': total,
            'Porcentaje': porcentaje,
            'Icono': icono_info['Icono'],
            'Color': icono_info['Color']
        })
    
    conn.close()
    
    return render_template(
        "dashboard/index.html",
        productos_bajo_stock=productos_bajo_stock,
        total_ventas=round(total_ventas, 2),
        porcentaje_ventas=porcentaje_ventas,
        total_transacciones=total_transacciones,
        porcentaje_transacciones=porcentaje_transacciones,
        ticket_promedio=ticket_promedio,
        porcentaje_ticket=porcentaje_ticket,
        productos_vendidos=productos_vendidos,
        porcentaje_productos=porcentaje_productos,
        fechas=fechas,
        ventas_diarias=ventas_diarias,
        categorias_labels=categorias_labels,
        categorias_data=categorias_data,
        productos_mas_vendidos=productos_mas_vendidos,
        ventas_recientes=ventas_recientes,
        categorias_populares=categorias_populares
    )