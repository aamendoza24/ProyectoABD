from flask import render_template, request, redirect, url_for, flash, jsonify, session
from app.blueprints.admin import admin_bp
from app.utils import role_required, login_required
from datetime import datetime

# Repositories
from app.repositories.empleado_repository import EmpleadoRepository
from app.repositories.usuario_repository import UsuarioRepository
from app.repositories.proveedor_repository import ProveedorRepository

# Services
from app.services.admin_service import AdminService

@admin_bp.route('/employees')
@role_required(['admin', 'gerente'])
def employees():
    """Página principal de administración de empleados"""
    try:
        employees = EmpleadoRepository.obtener_empleados_detallados()
        cargos = EmpleadoRepository.obtener_cargos()
        # sucursales se podrían sacar de SucursalRepository en el futuro
        from app.repositories.sucursal_repository import SucursalRepository
        sucursales = SucursalRepository.obtener_todas_las_sucursales()
        
        return render_template('admin/employees.html', 
                               employees=employees, 
                               cargos=cargos, 
                               sucursales=sucursales,
                               current_year=datetime.now().year)
    except Exception as e:
        flash(f"Error al cargar la página: {str(e)}", "danger")
        return redirect(url_for('dashboard.index'))

@admin_bp.route('/get-employee-details')
@role_required(['admin', 'gerente'])
def get_employee_details():
    """Obtener detalles de un empleado para mostrar en modal"""
    employee_id = request.args.get('employeeId')
    if not employee_id:
        return jsonify({'success': False, 'message': 'ID de empleado no proporcionado'})
    
    try:
        employee = EmpleadoRepository.obtener_empleado_detallado_por_id(employee_id)
        if not employee:
            return jsonify({'success': False, 'message': 'Empleado no encontrado'})
        
        if employee.get('last_login'):
            try:
                last_login = datetime.strptime(employee['last_login'], '%Y-%m-%d %H:%M:%S')
                employee['last_login'] = last_login.strftime('%d/%m/%Y %H:%M:%S')
            except:
                pass
                
        activity_list = []
        if employee.get('user_id'):
            activity = UsuarioRepository.obtener_actividad_reciente(employee['user_id'], limit=10)
            for item in activity:
                try:
                    timestamp = datetime.strptime(item['timestamp'], '%Y-%m-%d %H:%M:%S')
                    item['timestamp'] = timestamp.strftime('%d/%m/%Y %H:%M:%S')
                except:
                    pass
                activity_list.append(item)
        
        return jsonify({
            'success': True,
            'employee': employee,
            'activity': activity_list
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@admin_bp.route('/add-employee', methods=['POST'])
@role_required(['admin'])
def add_employee():
    """Añadir un nuevo empleado"""
    try:
        datos_empleado = {
            'nombre': request.form.get('nombreCompleto'),
            'cargo_id': request.form.get('cargo'),
            'sucursal_id': request.form.get('sucursal')
        }
        datos_usuario = {
            'username': request.form.get('username'),
            'email': request.form.get('email'),
            'password': request.form.get('password'),
            'role': request.form.get('role'),
            'is_active': ('isActive' in request.form)
        }
        
        success, msg = AdminService.crear_empleado_y_usuario(datos_empleado, datos_usuario, session.get('user_id'), request.remote_addr)
        flash(msg, "success" if success else "danger")
    except ValueError as val_e:
        flash(str(val_e), "danger")
    except Exception as e:
        flash(f"Error al añadir empleado: {str(e)}", "danger")
        
    return redirect(url_for('admin.employees'))

@admin_bp.route('/edit-employee', methods=['POST'])
@role_required(['admin'])
def edit_employee():
    """Editar un empleado existente"""
    try:
        datos_empleado = {
            'empleado_id': request.form.get('employeeId'),
            'nombre': request.form.get('nombreCompleto'),
            'cargo_id': request.form.get('cargo'),
            'sucursal_id': request.form.get('sucursal')
        }
        datos_usuario = {
            'username': request.form.get('username'),
            'email': request.form.get('email'),
            'password': request.form.get('password'),
            'role': request.form.get('role'),
            'is_active': ('isActive' in request.form)
        }
        
        success, msg = AdminService.editar_empleado_y_usuario(datos_empleado, datos_usuario, session.get('user_id'), request.remote_addr)
        flash(msg, "success" if success else "danger")
    except ValueError as val_e:
        flash(str(val_e), "danger")
    except Exception as e:
        flash(f"Error al actualizar empleado: {str(e)}", "danger")
        
    return redirect(url_for('admin.employees'))

@admin_bp.route('/toggle-employee-status', methods=['POST'])
@role_required(['admin'])
def toggle_employee_status():
    """Habilitar o deshabilitar un empleado"""
    try:
        employee_id = request.form.get('employeeId')
        action = request.form.get('action')
        
        if not employee_id or action not in ['enable', 'disable']:
            return jsonify({'success': False, 'message': 'Parámetros inválidos'})
            
        is_active = (action == 'enable')
        success, msg = AdminService.alternar_estado_usuario(employee_id, is_active, session.get('user_id'), request.remote_addr)
        
        return jsonify({'success': success, 'message': msg})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@admin_bp.route('/toggle-employee-lock', methods=['POST'])
@role_required(['admin'])
def toggle_employee_lock():
    """Bloquear o desbloquear un empleado"""
    try:
        employee_id = request.form.get('employeeId')
        action = request.form.get('action')
        
        if not employee_id or action not in ['lock', 'unlock']:
            return jsonify({'success': False, 'message': 'Parámetros inválidos'})
            
        is_locked = (action == 'lock')
        success, msg = AdminService.alternar_bloqueo_usuario(employee_id, is_locked, session.get('user_id'), request.remote_addr)
        
        return jsonify({'success': success, 'message': msg})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@admin_bp.route('/delete-employee', methods=['POST'])
@role_required(['admin'])
def delete_employee():
    """Eliminar un empleado"""
    try:
        employee_id = request.form.get('employeeId')
        if not employee_id:
            flash("ID de empleado no proporcionado", "danger")
            return redirect(url_for('admin.employees'))
            
        success, msg = AdminService.eliminar_empleado_completo(employee_id)
        flash(msg, "success" if success else "danger")
    except Exception as e:
        flash(f"Error al eliminar empleado: {str(e)}", "danger")
        
    return redirect(url_for('admin.employees'))

# --- RUTAS PARA PROVEEDORES ---

@admin_bp.route('/proveedores')
@login_required
@role_required(['admin', 'gerente'])
def proveedores():
    proveedores = ProveedorRepository.obtener_todos_los_proveedores()
    return render_template('admin/proveedores.html', proveedores=proveedores)

@admin_bp.route('/add_proveedor', methods=['POST'])
@login_required
def add_proveedor():
    try:
        nombre = request.form.get('nombre')
        telefono = request.form.get('telefono')
        email = request.form.get('email')
        direccion = request.form.get('direccion')
        
        ProveedorRepository.crear_proveedor(nombre, telefono, email, direccion)
        flash('Proveedor añadido correctamente', 'success')
    except Exception as e:
        flash(f'Error al añadir proveedor: {str(e)}', 'danger')
    return redirect(url_for('admin.proveedores'))

@admin_bp.route('/edit_proveedor', methods=['POST'])
@login_required
def edit_proveedor():
    try:
        proveedor_id = request.form.get('proveedorId')
        nombre = request.form.get('nombre')
        telefono = request.form.get('telefono')
        email = request.form.get('email')
        direccion = request.form.get('direccion')

        ProveedorRepository.actualizar_proveedor(proveedor_id, nombre, telefono, email, direccion)
        flash('Proveedor actualizado correctamente', 'success')
    except Exception as e:
        flash(f'Error al actualizar proveedor: {str(e)}', 'danger')
    return redirect(url_for('admin.proveedores'))

@admin_bp.route('/delete_proveedor', methods=['POST'])
@login_required
def delete_proveedor():
    try:
        proveedor_id = request.form.get('proveedorId')
        tienen_compras = ProveedorRepository.verificar_compras_asociadas(proveedor_id)
        
        if tienen_compras:
            flash('No se puede eliminar el proveedor porque tiene compras asociadas', 'warning')
        else:
            ProveedorRepository.eliminar_proveedor(proveedor_id)
            flash('Proveedor eliminado correctamente', 'success')
    except Exception as e:
        flash(f'Error al eliminar proveedor: {str(e)}', 'danger')
    return redirect(url_for('admin.proveedores'))

@admin_bp.route('/get_proveedor_details')
@login_required
def get_proveedor_details():
    try:
        proveedor_id = request.args.get('proveedorId')
        proveedor = ProveedorRepository.obtener_proveedor_por_id(proveedor_id)
        
        if not proveedor:
            return jsonify({'success': False, 'message': 'Proveedor no encontrado'})

        compras = ProveedorRepository.obtener_compras_recientes_proveedor(proveedor_id)
        compras_data = [{'id': c['IDCompra'], 'fecha': c['Fecha'], 'total': float(c['Total']) if c['Total'] else 0} for c in compras]

        return jsonify({
            'success': True,
            'proveedor': {
                'id': proveedor['IDProveedor'],
                'nombre': proveedor['Nombre'],
                'telefono': proveedor['Telefono'],
                'email': proveedor['Email'],
                'direccion': proveedor['DireccionCompleta']
            },
            'compras': compras_data
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})