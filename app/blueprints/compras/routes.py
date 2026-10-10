from flask import Blueprint, render_template, request, flash, jsonify, send_file, redirect, url_for
from datetime import datetime, timedelta
from app.utils import login_required, role_required
from app.blueprints.compras import compras_bp

# Repositorios
from app.repositories.compra_repository import CompraRepository
from app.repositories.proveedor_repository import ProveedorRepository
from app.repositories.sucursal_repository import SucursalRepository
from app.repositories.reporte_repository import ReporteRepository
from app.repositories.producto_repository import ProductoRepository

# Servicios
from app.services.compra_service import CompraService
from app.services.reporte_service import ReporteService

@compras_bp.route('/', methods=['GET', 'POST'])
@login_required
@role_required(['admin', 'gerente', 'empleado', 'almacen'])
def index():
    """Ruta para generar nueva compra"""
    if request.method == 'POST':
        try:
            data = request.get_json()
            resultado = CompraService.registrar_compra(data)
            return jsonify(resultado)
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})
            
    proveedores = ProveedorRepository.obtener_todos_los_proveedores()
    sucursales = SucursalRepository.obtener_todas_las_sucursales()
    today_date = datetime.now().strftime('%Y-%m-%d')
    
    return render_template(
        'compras/compras.html',
        proveedores=proveedores,
        sucursales=sucursales,
        today_date=today_date
    )

@compras_bp.route('/buscar_productos')
@login_required
def buscar_productos():
    query = request.args.get('q', '')
    if not query:
        return jsonify([])
    
    # Podemos re-usar producto_repository
    # En caso de no tener metodo exácto de LIKE limit 10, usamos algo genérico:
    import sqlite3
    from app.utils.db import get_db_connection
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    productos = conn.execute('''
        SELECT p.IDProducto, p.Nombre, p.Precio
        FROM Producto p
        WHERE p.Nombre LIKE ?
        ORDER BY p.Nombre
        LIMIT 10
    ''', (f'%{query}%',)).fetchall()
    conn.close()
    
    return jsonify([dict(p) for p in productos])

@compras_bp.route('/historial-compras', methods=['GET'])
@role_required(['admin', 'gerente', 'empleado', 'almacen'])
def historial_compras():
    """Página de historial de compras"""
    try:
        compras = CompraRepository.obtener_historial_compras()
        proveedores = ProveedorRepository.obtener_todos_los_proveedores()
        sucursales = SucursalRepository.obtener_todas_las_sucursales()
        
        return render_template(
            'compras/historial_compras.html', 
            compras=compras, 
            proveedores=proveedores, 
            sucursales=sucursales
        )
    except Exception as e:
        flash(f"Error al cargar el historial de compras: {str(e)}", "error")
        return redirect(url_for('dashboard.index'))

@compras_bp.route('/api/compras/filtrar', methods=['GET'])
@compras_bp.route('/historial-compras/filtrar', methods=['GET'])
@role_required(['admin', 'gerente', 'empleado', 'almacen'])
def filtrar_compras():
    """API para filtrar compras según criterios (usado por la tabla AJAX)"""
    try:
        filtros = {
            'fecha_inicio': request.args.get('fecha_inicio'),
            'fecha_fin': request.args.get('fecha_fin'),
            'proveedor_id': request.args.get('proveedor_id'),
            'sucursal_id': request.args.get('sucursal_id')
        }
        
        compras = CompraRepository.obtener_historial_compras(filtros)
        
        return jsonify({
            'compras': compras,
            'total_compras': len(compras),
            'monto_total': sum(c['Total'] for c in compras)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@compras_bp.route('/api/compras/detalle/<int:compra_id>', methods=['GET'])
@compras_bp.route('/historial-compras/detalle/<int:compra_id>', methods=['GET'])
@compras_bp.route('/detalles_json/<int:compra_id>', methods=['GET'])
@role_required(['admin', 'gerente', 'empleado', 'almacen'])
def detalle_compra(compra_id):
    """API para obtener el detalle de una compra específica"""
    try:
        compra = CompraRepository.obtener_compra_por_id(compra_id)
        if not compra:
            return jsonify({'error': 'Compra no encontrada'}), 404
            
        detalles = CompraRepository.obtener_detalles_compra(compra_id)
        
        # Compatibilidad con múltiples formas de llamarlo en plantillas anteriores
        compra['detalles'] = detalles
        
        # Formato para la ruta antigua `detalles_json`
        return jsonify({
            'compra': {
                'id': compra['IDCompra'],
                'fecha': compra['Fecha'],
                'total': compra['Total'],
                'proveedor': compra.get('Proveedor'),
                'sucursal': compra.get('Sucursal'),
                'referencia': compra.get('Detalle', '')
            },
            'detalles': [
                {
                    'id': d['IDDetalleCompra'],
                    'producto': d['producto'] if 'producto' in d else d.get('Producto'),
                    'producto_id': d['IDProducto'],
                    'cantidad': d['Cantidad'],
                    'precio_unitario': d['PrecioCompra'],
                    'subtotal': d['Subtotal']
                } for d in detalles
            ],
            **compra # Mezclamos flat values tambien
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@compras_bp.route('/reporte')
@role_required(['admin', 'gerente'])
def reporte():
    """Página principal de reportes de compras"""
    try:
        seis_meses_atras = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
        
        return render_template(
            'compras/reporte_compras.html', 
            sucursales=SucursalRepository.obtener_todas_las_sucursales(),
            proveedores=ProveedorRepository.obtener_todos_los_proveedores(),
            estadisticas=ReporteRepository.obtener_estadisticas_mensuales_compras(),
            compras_recientes=ReporteRepository.obtener_compras_recientes(10),
            datos_grafico_meses=ReporteRepository.obtener_grafico_compras_por_mes(seis_meses_atras),
            datos_grafico_proveedores=ReporteRepository.obtener_grafico_compras_por_proveedor(seis_meses_atras),
            datos_grafico_sucursales=ReporteRepository.obtener_grafico_compras_por_sucursal(seis_meses_atras),
            productos_mas_comprados=ReporteRepository.obtener_top_productos_comprados(seis_meses_atras, 10)
        )
    except Exception as e:
        return render_template('error.html', error=str(e))

@compras_bp.route('/exportar/compras', methods=['GET'])
@role_required(['admin', 'gerente'])
def exportar_compras():
    """Exportar reporte de compras a Excel"""
    try:
        filtros = {
            'fecha_inicio': request.args.get('fecha_inicio'),
            'fecha_fin': request.args.get('fecha_fin'),
            'proveedor_id': request.args.get('proveedor_id'),
            'sucursal_id': request.args.get('sucursal_id')
        }
        
        output = ReporteService.exportar_compras_excel(filtros)
        
        if not output:
             return "No hay datos para exportar con los filtros seleccionados", 404
             
        fecha_actual = datetime.now().strftime('%Y%m%d')
        nombre_archivo = f"Reporte_Compras_{fecha_actual}.xlsx"
        
        return send_file(
            output,
            as_attachment=True,
            download_name=nombre_archivo,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        return str(e), 500

@compras_bp.route('/exportar_pdf/<int:compra_id>')
@login_required
def exportar_pdf(compra_id):
    return jsonify({'success': True, 'message': 'Función no implementada'})