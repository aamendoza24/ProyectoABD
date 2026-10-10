from flask import Blueprint, render_template, request, flash, jsonify, session, send_file
from datetime import datetime, date, timedelta
from app.utils import login_required, role_required
from app.blueprints.ventas import ventas_bp

from app.repositories.venta_repository import VentaRepository
from app.repositories.cliente_repository import ClienteRepository
from app.repositories.reporte_repository import ReporteRepository
from app.services.venta_service import VentaService
from app.services.reporte_service import ReporteService
from app.utils.db import get_db_connection
import json

import sqlite3

@ventas_bp.route('/catalogo')
@role_required(['admin', 'gerente', 'vendedor'])
def catalogo():
    """Muestra los productos en el apartado de venta (POS)"""
    productos, categorias = VentaRepository.obtener_catalogo_para_venta(id_sucursal=1)
    return render_template("ventas/realizar_venta.html", productos=productos, categorias=categorias)

@ventas_bp.route("/guardar_venta", methods=["POST"])
def guardar_venta():
    """Valida y procesa el carrito de compras generando la venta"""
    data = request.get_json()
    user_id = session.get("user_id")

    # Obtener el IDEmpleado desde el usuario en sesión (Podríamos poner esto en un UserService si hubiese)
    conexion = get_db_connection()
    try:
        cursor = conexion.cursor()
        cursor.execute("SELECT IDEmpleado FROM usuarios WHERE id = ?", (user_id,))
        empleado = cursor.fetchone()
        if not empleado:
            return jsonify({"error": "No se encontró el empleado asociado al usuario"}), 400
        id_empleado = empleado["IDEmpleado"]
    finally:
        conexion.close()

    try:
        respuesta = VentaService.procesar_y_guardar_venta(
            datos_carrito=data, 
            empleado_id=id_empleado, 
            sucursal_id=1
        )
        return jsonify(respuesta), 200
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": "No se pudo guardar la venta", "details": str(e)}), 500

@ventas_bp.route("/historial", methods=["GET", "POST"])
@role_required(['admin', 'gerente', 'vendedor'])
def historial():
    """Ruta para el historial de ventas"""
    if request.method == "POST":
        data = request.json
        filtro = data.get("filtro", "todas")
        fecha_inicio = data.get("fecha_inicio") if filtro == "personalizado" else None
        fecha_fin = data.get("fecha_fin") if filtro == "personalizado" else None
        cliente_id = data.get("cliente_id") if filtro == "personalizado" else None
        
        ventas = VentaRepository.obtener_ventas_filtradas(filtro, fecha_inicio, fecha_fin, cliente_id)
        return jsonify({"ventas": ventas})
    
    ventas = VentaRepository.obtener_ventas_filtradas("todas")
    clientes = ClienteRepository.obtener_todos_los_clientes()
    return render_template("ventas/ventas.html", ventas=ventas, clientes=clientes)

@ventas_bp.route("/detalles_venta/<int:id_venta>", methods=["GET"])
def detalles_venta(id_venta):
    """Ruta que retorna todos los detalles de la venta"""
    venta = VentaRepository.obtener_venta_por_id(id_venta)
    if not venta:
        return jsonify({"error": "Venta no encontrada"}), 404
        
    detalles = VentaRepository.obtener_detalles_venta(id_venta)
    return jsonify({"venta": venta, "detalles": detalles})

@ventas_bp.route('/buscar-clientes', methods=['POST'])
def buscar_clientes():
    """Búsqueda autocompletar de clientes en la vista finalizar venta"""
    try:
        termino = request.json.get('termino', '').strip()
        if len(termino) < 2:
            return jsonify({'error': 'Ingrese al menos 2 caracteres para buscar'}), 400
            
        resultados = ClienteRepository.buscar_clientes_por_termino(termino)
        return jsonify({'clientes': resultados})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ----- RUTAS DE REPORTES CLÁSICOS -----
@ventas_bp.route("/reporte")
@role_required(['admin', 'gerente'])
def reporte():
    fecha_actual = datetime.now().strftime('%Y-%m-%d')
    # Podría construirse usando ReporteService para todo, pero dejaremos llamadas atadas para compatibilidad:
    
    # Kpis basicos e ingresos del mes (30 dias aprox):
    fecha_inicio_mes = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    filtros_mes = {'fecha_inicio': fecha_inicio_mes, 'fecha_fin': fecha_actual}
    kpis = ReporteRepository.obtener_kpis_basicos(fecha_inicio_mes, fecha_actual)
    
    # 10. Total productos vendidos
    total_productos_vendidos = ReporteRepository.obtener_kpi_general('Detalle_Venta DV JOIN Venta V ON V.IDVenta = DV.IDVenta', 'DV.Cantidad', f"V.Fecha >= date('now', '-30 days')")
    
    # Categorias para filtros
    conexion = get_db_connection()
    try:
        cursor = conexion.cursor()
        cursor.execute("SELECT IDCategoria, Nombre FROM Categoria ORDER BY Nombre")
        categorias = [dict(row) for row in cursor.fetchall()]
    finally:
        conexion.close()
        
    # Usando el ReporteRepository para el resto:
    ventas_brutas = ReporteRepository.obtener_ventas_agrupadas_por_fecha(None, None)
    
    # Calcular crecimiento en Python
    ventas_con_crecimiento = []
    anterior = 0
    for v in ventas_brutas:
        actual = v['TotalVentas']
        v['Crecimiento'] = round(actual - anterior, 2) if anterior > 0 else 0
        ventas_con_crecimiento.append(v)
        anterior = actual
        
    ventas_recientes_dashboard = ventas_con_crecimiento[-7:]
    
    fechas = [row["Fecha"] for row in ventas_recientes_dashboard]
    totales = [row["TotalVentas"] for row in ventas_recientes_dashboard]
    
    top_productos = ReporteRepository.obtener_top_productos({'recent_days': 6})
    nombres_productos = [p["Nombre"] for p in top_productos]
    cantidades_vendidas = [p["TotalVendido"] for p in top_productos]
    
    ventas_recientes = ReporteRepository.obtener_ventas_recientes(5)
    productos_rendimiento = ReporteRepository.obtener_top_productos({'fecha_inicio': fecha_inicio_mes, 'fecha_fin': fecha_actual}, limit=20)
    
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
        total_ventas_periodo=kpis['TotalVentas'] or 0,
        porcentaje_crecimiento_ventas=0, # dummy por rapidez / se calcula en balance completo
        ticket_promedio=round(kpis['TicketPromedio'] or 0, 2),
        porcentaje_crecimiento_ticket=0,
        total_transacciones=kpis['TotalTransacciones'],
        porcentaje_crecimiento_transacciones=0,
        total_productos_vendidos=total_productos_vendidos,
        porcentaje_crecimiento_productos=0,
        categorias=categorias,
        productos_rendimiento=productos_rendimiento
    )

@ventas_bp.route("/dashboard_datos", methods=["POST"])
@role_required(['admin', 'gerente'])
def dashboard_datos():
    data = request.get_json()
    fecha_inicio = data.get("fecha_inicio")
    fecha_fin = data.get("fecha_fin")

    ventas = ReporteRepository.obtener_ventas_agrupadas_por_fecha(fecha_inicio, fecha_fin)
    fechas = [row["Fecha"] for row in ventas]
    totales = [row["TotalVentas"] for row in ventas]
    
    kpis = ReporteRepository.obtener_kpis_basicos(fecha_inicio, fecha_fin)
    total_ventas = kpis["TotalVentas"] or 0
    total_transacciones = kpis["TotalTransacciones"] or 0
    ticket_promedio = kpis["TicketPromedio"] or 0

    top_productos = ReporteRepository.obtener_top_productos({'fecha_inicio': fecha_inicio, 'fecha_fin': fecha_fin})
    nombres_productos = [p["Nombre"] for p in top_productos]
    cantidades_vendidas = [p["TotalVendido"] for p in top_productos]

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
    productos = ReporteRepository.obtener_top_productos({
        'fecha_inicio': data.get("fecha_inicio"),
        'fecha_fin': data.get("fecha_fin"),
        'id_categoria': data.get("id_categoria")
    }, limit=20)
    
    # Calcular %
    total_ventas_productos = sum(p["TotalVentas"] for p in productos)
    for p in productos:
        p["PorcentajeTotal"] = round((p["TotalVentas"] / total_ventas_productos * 100), 2) if total_ventas_productos > 0 else 0
        p["UnidadesVendidas"] = p["TotalVendido"]
        
    return jsonify({"productos": productos})

# ----- RUTAS DEL BALANCE GENERAL -----
@ventas_bp.route('/balance')
def balance():
    """Página principal del balance general"""
    conexion = get_db_connection()
    try:
        conexion.row_factory = sqlite3.Row
        categorias = [dict(r) for r in conexion.execute('SELECT IDCategoria, Nombre FROM Categoria ORDER BY Nombre').fetchall()]
        sucursales = [dict(r) for r in conexion.execute('SELECT IDSucursal, Nombre FROM Sucursal ORDER BY Nombre').fetchall()]
    finally:
        conexion.close()
    return render_template('reportes/balance.html', categorias=categorias, sucursales=sucursales)

@ventas_bp.route('/balance/data', methods=['POST'])
def balance_data():
    try:
        filters = request.json or {}
        return jsonify({
            'kpis': ReporteService.get_kpis(filters),
            'top_products': ReporteRepository.obtener_top_productos(filters, limit=5),
            'transactions': ReporteService.get_transactions(filters)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@ventas_bp.route('/balance/chart', methods=['POST'])
def balance_chart():
    try:
        data = request.json or {}
        filters = {k: v for k, v in data.items() if k != 'period'}
        period = data.get('period', 'monthly')
        return jsonify(ReporteService.get_income_expense_chart_data(filters, period))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@ventas_bp.route('/balance/transactions', methods=['POST'])
def balance_transactions():
    try:
        data = request.json or {}
        filters = {k: v for k, v in data.items() if k != 'group_by'}
        group_by = data.get('group_by', 'daily')
        return jsonify({'transactions': ReporteService.get_grouped_transactions(filters, group_by)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@ventas_bp.route('/balance/export/pdf', methods=['POST'])
def export_pdf():
    try:
        filters = request.json or {}
        buffer = ReporteService.generate_pdf_report(filters)
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f'balance_general_{date.today().strftime("%Y%m%d")}.pdf',
            mimetype='application/pdf'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@ventas_bp.route('/balance/export/excel', methods=['POST'])
def export_excel():
    try:
        filters = request.json or {}
        buffer = ReporteService.generate_excel_report(filters)
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f'balance_general_{date.today().strftime("%Y%m%d")}.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@ventas_bp.route('/balance/note', methods=['POST'])
def save_note():
    try:
        data = request.json
        title = data.get('title')
        content = data.get('content')
        filters = data.get('filters', {})
        
        conn = get_db_connection()
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
        conn.execute('INSERT INTO report_notes (title, content, filters) VALUES (?, ?, ?)', 
                     (title, content, json.dumps(filters)))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
