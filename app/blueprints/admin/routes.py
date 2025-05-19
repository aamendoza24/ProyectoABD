# app/blueprints/admin/routes.py
from flask import render_template, request, redirect, url_for, flash, jsonify, session
from app.blueprints.admin import admin_bp
from app.utils.db import get_db_connection
from app.utils import role_required
import bcrypt
from datetime import datetime, timedelta
import sqlite3

@admin_bp.route('/employees')
@role_required(['admin', 'gerente'])
def employees():
    """Página principal de administración de empleados"""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        
        
        # Obtener todos los empleados con información de usuario
        cursor.execute("""
            SELECT e.IDEmpleado, e.NombreCompleto, c.Nombre as cargo_nombre, e.IDCargo,
                   u.id as user_id, u.user, u.email, u.role, u.is_active, u.account_locked,
                   u.last_login, s.Nombre as sucursal_nombre, s.IDSucursal
            FROM Empleado e
            LEFT JOIN usuarios u ON e.IDEmpleado = u.IDEmpleado
            LEFT JOIN Cargo c ON e.IDCargo = c.IDCargo
            LEFT JOIN Sucursal s ON 1=1  -- Aquí deberías tener una relación entre empleado y sucursal
            ORDER BY e.NombreCompleto
        """)
        employees = cursor.fetchall()
        
        # Obtener todos los cargos
        cursor.execute("SELECT IDCargo, Nombre FROM Cargo ORDER BY Nombre")
        cargos = cursor.fetchall()
        
        # Obtener todas las sucursales
        cursor.execute("SELECT IDSucursal, Nombre FROM Sucursal ORDER BY Nombre")
        sucursales = cursor.fetchall()
        
        return render_template('admin/employees.html', 
                               employees=employees, 
                               cargos=cargos, 
                               sucursales=sucursales,
                               current_year=datetime.now().year)
    
    except Exception as e:
        flash(f"Error al cargar la página: {str(e)}", "danger")
        return redirect(url_for('dashboard.index'))
    finally:
        if conn:
            conn.close()

@admin_bp.route('/get-employee-details')
@role_required(['admin', 'gerente'])
def get_employee_details():
    """Obtener detalles de un empleado para mostrar en modal"""
    employee_id = request.args.get('employeeId')
    
    if not employee_id:
        return jsonify({'success': False, 'message': 'ID de empleado no proporcionado'})
    
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Obtener información del empleado
        cursor.execute("""
            SELECT e.IDEmpleado, e.NombreCompleto, c.Nombre as cargo_nombre, e.IDCargo,
                   u.id as user_id, u.user, u.email, u.role, u.is_active, u.account_locked,
                   u.last_login, s.Nombre as sucursal_nombre, s.IDSucursal
            FROM Empleado e
             JOIN usuarios u ON e.IDEmpleado = u.IDEmpleado
             JOIN Cargo c ON e.IDCargo = c.IDCargo
             JOIN Sucursal s ON s.IDSucursal=1  -- Aquí deberías tener una relación entre empleado y sucursal
            WHERE e.IDEmpleado = ?
        """, (employee_id,))
        employee = cursor.fetchone()

        print(employee)
        
        if not employee:
            return jsonify({'success': False, 'message': 'Empleado no encontrado'})
        
        # Convertir a diccionario para poder serializarlo
        employee_dict = dict(employee)
        
        # Formatear la fecha de último login si existe
        if employee_dict['last_login']:
            try:
                last_login = datetime.strptime(employee_dict['last_login'], '%Y-%m-%d %H:%M:%S')
                employee_dict['last_login'] = last_login.strftime('%d/%m/%Y %H:%M:%S')
            except:
                pass
        
        # Obtener actividad reciente del usuario
        cursor.execute("""
            SELECT activity_type, description, timestamp
            FROM user_activity_log
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT 10
        """, (employee_dict['user_id'],))
        activity = cursor.fetchall()
        
        # Convertir actividad a lista de diccionarios
        activity_list = []
        for item in activity:
            activity_dict = dict(item)
            try:
                timestamp = datetime.strptime(activity_dict['timestamp'], '%Y-%m-%d %H:%M:%S')
                activity_dict['timestamp'] = timestamp.strftime('%d/%m/%Y %H:%M:%S')
            except:
                pass
            activity_list.append(activity_dict)
        
        return jsonify({
            'success': True,
            'employee': employee_dict,
            'activity': activity_list
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})
    finally:
        if conn:
            conn.close()

@admin_bp.route('/add-employee', methods=['POST'])
@role_required(['admin'])
def add_employee():
    """Añadir un nuevo empleado"""
    try:
        # Obtener datos del formulario
        nombre_completo = request.form.get('nombreCompleto')
        cargo_id = request.form.get('cargo')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')
        sucursal_id = request.form.get('sucursal')
        is_active = 'isActive' in request.form
        
        # Validar datos
        if not all([nombre_completo, cargo_id, username, email, password, role, sucursal_id]):
            flash("Todos los campos son obligatorios", "danger")
            return redirect(url_for('admin.employees'))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verificar si el usuario ya existe
        cursor.execute("SELECT id FROM usuarios WHERE user = ? OR email = ?", (username, email))
        existing_user = cursor.fetchone()
        
        if existing_user:
            flash("El nombre de usuario o correo electrónico ya está en uso", "danger")
            return redirect(url_for('admin.employees'))
        
        # Insertar empleado
        cursor.execute("""
            INSERT INTO Empleado (NombreCompleto, IDCargo)
            VALUES (?, ?)
        """, (nombre_completo, cargo_id))
        
        # Obtener el ID del empleado recién insertado
        employee_id = cursor.lastrowid
        
        # Hashear la contraseña
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        # Insertar usuario
        cursor.execute("""
            INSERT INTO usuarios (user, email, contrasena, role, is_active, IDEmpleado)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (username, email, hashed_password, role, is_active, employee_id))
        
        # Registrar actividad
        user_id = cursor.lastrowid
        admin_id = session.get('user_id')
        
        cursor.execute("""
            INSERT INTO user_activity_log (user_id, activity_type, description, ip_address)
            VALUES (?, ?, ?, ?)
        """, (user_id, "Cuenta Creada", f"Cuenta creada por administrador (ID: {admin_id})", request.remote_addr))
        
        conn.commit()
        
        flash("Empleado añadido exitosamente", "success")
        return redirect(url_for('admin.employees'))
    
    except Exception as e:
        flash(f"Error al añadir empleado: {str(e)}", "danger")
        return redirect(url_for('admin.employees'))
    finally:
        if conn:
            conn.close()

@admin_bp.route('/edit-employee', methods=['POST'])
@role_required(['admin'])
def edit_employee():
    """Editar un empleado existente"""
    try:
        # Obtener datos del formulario
        employee_id = request.form.get('employeeId')
        nombre_completo = request.form.get('nombreCompleto')
        cargo_id = request.form.get('cargo')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')
        sucursal_id = request.form.get('sucursal')
        is_active = 'isActive' in request.form
        
        # Validar datos
        if not all([employee_id, nombre_completo, cargo_id, username, email, role, sucursal_id]):
            flash("Todos los campos son obligatorios excepto la contraseña", "danger")
            return redirect(url_for('admin.employees'))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verificar si el empleado existe
        cursor.execute("SELECT IDEmpleado FROM Empleado WHERE IDEmpleado = ?", (employee_id,))
        existing_employee = cursor.fetchone()
        
        if not existing_employee:
            flash("Empleado no encontrado", "danger")
            return redirect(url_for('admin.employees'))
        
        # Verificar si el usuario ya existe (excluyendo el usuario actual)
        cursor.execute("""
            SELECT id FROM usuarios 
            WHERE (user = ? OR email = ?) AND IDEmpleado != ?
        """, (username, email, employee_id))
        existing_user = cursor.fetchone()
        
        if existing_user:
            flash("El nombre de usuario o correo electrónico ya está en uso por otro empleado", "danger")
            return redirect(url_for('admin.employees'))
        
        # Actualizar empleado
        cursor.execute("""
            UPDATE Empleado 
            SET NombreCompleto = ?, IDCargo = ?
            WHERE IDEmpleado = ?
        """, (nombre_completo, cargo_id, employee_id))
        
        # Obtener el ID de usuario asociado al empleado
        cursor.execute("SELECT id FROM usuarios WHERE IDEmpleado = ?", (employee_id,))
        user_result = cursor.fetchone()
        
        if user_result:
            user_id = user_result[0]
            
            # Preparar la consulta para actualizar el usuario
            update_query = """
                UPDATE usuarios 
                SET user = ?, email = ?, role = ?, is_active = ?
                WHERE id = ?
            """
            params = [username, email, role, is_active, user_id]
            
            # Si se proporciona una nueva contraseña, actualizarla
            if password:
                hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
                update_query = """
                    UPDATE usuarios 
                    SET user = ?, email = ?, contrasena = ?, role = ?, is_active = ?
                    WHERE id = ?
                """
                params = [username, email, hashed_password, role, is_active, user_id]
            
            cursor.execute(update_query, params)
            
            # Registrar actividad
            admin_id = session.get('user_id')
            cursor.execute("""
                INSERT INTO user_activity_log (user_id, activity_type, description, ip_address)
                VALUES (?, ?, ?, ?)
            """, (user_id, "Cuenta Actualizada", f"Cuenta actualizada por administrador (ID: {admin_id})", request.remote_addr))
        else:
            # Si no existe un usuario asociado, crear uno nuevo
            hashed_password = bcrypt.hashpw(password.encode('utf-8') if password else "changeme123".encode('utf-8'), bcrypt.gensalt())
            
            cursor.execute("""
                INSERT INTO usuarios (user, email, contrasena, role, is_active, IDEmpleado, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (username, email, hashed_password, role, is_active, employee_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            
            # Registrar actividad
            user_id = cursor.lastrowid
            admin_id = session.get('user_id')
            cursor.execute("""
                INSERT INTO user_activity_log (user_id, activity_type, description, ip_address)
                VALUES (?, ?, ?, ?)
            """, (user_id, "Cuenta Creada", f"Cuenta creada por administrador (ID: {admin_id})", request.remote_addr))
        
        conn.commit()
        
        flash("Empleado actualizado exitosamente", "success")
        return redirect(url_for('admin.employees'))
    
    except Exception as e:
        flash(f"Error al actualizar empleado: {str(e)}", "danger")
        return redirect(url_for('admin.employees'))
    finally:
        if conn:
            conn.close()

@admin_bp.route('/toggle-employee-status', methods=['POST'])
@role_required(['admin'])
def toggle_employee_status():
    """Habilitar o deshabilitar un empleado"""
    try:
        employee_id = request.form.get('employeeId')
        action = request.form.get('action')  # 'enable' o 'disable'
        
        if not employee_id or action not in ['enable', 'disable']:
            return jsonify({'success': False, 'message': 'Parámetros inválidos'})
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Obtener el ID de usuario asociado al empleado
        cursor.execute("SELECT id FROM usuarios WHERE IDEmpleado = ?", (employee_id,))
        user_result = cursor.fetchone()
        
        if not user_result:
            return jsonify({'success': False, 'message': 'Usuario no encontrado'})
        
        user_id = user_result[0]
        is_active = action == 'enable'
        
        # Actualizar estado del usuario
        cursor.execute("""
            UPDATE usuarios 
            SET is_active = ?
            WHERE id = ?
        """, (is_active, user_id))
        
        # Registrar actividad
        admin_id = session.get('user_id')
        activity_type = "Cuenta Activada" if is_active else "Cuenta Desactivada"
        cursor.execute("""
            INSERT INTO user_activity_log (user_id, activity_type, description, ip_address)
            VALUES (?, ?, ?, ?)
        """, (user_id, activity_type, f"Acción realizada por administrador (ID: {admin_id})", request.remote_addr))
        
        conn.commit()
        
        message = "Empleado habilitado exitosamente" if is_active else "Empleado deshabilitado exitosamente"
        return jsonify({'success': True, 'message': message})
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})
    finally:
        if conn:
            conn.close()

@admin_bp.route('/toggle-employee-lock', methods=['POST'])
@role_required(['admin'])
def toggle_employee_lock():
    """Bloquear o desbloquear un empleado"""
    try:
        employee_id = request.form.get('employeeId')
        action = request.form.get('action')  # 'lock' o 'unlock'
        
        if not employee_id or action not in ['lock', 'unlock']:
            return jsonify({'success': False, 'message': 'Parámetros inválidos'})
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Obtener el ID de usuario asociado al empleado
        cursor.execute("SELECT id FROM usuarios WHERE IDEmpleado = ?", (employee_id,))
        user_result = cursor.fetchone()
        
        if not user_result:
            return jsonify({'success': False, 'message': 'Usuario no encontrado'})
        
        user_id = user_result[0]
        account_locked = action == 'lock'
        
        # Actualizar estado de bloqueo del usuario
        if account_locked:
            # Bloquear cuenta por 24 horas
            locked_until = datetime.now() + timedelta(hours=24)
            cursor.execute("""
                UPDATE usuarios 
                SET account_locked = 1, locked_until = ?, failed_login_attempts = 5
                WHERE id = ?
            """, (locked_until.strftime('%Y-%m-%d %H:%M:%S'), user_id))
        else:
            # Desbloquear cuenta
            cursor.execute("""
                UPDATE usuarios 
                SET account_locked = 0, locked_until = NULL, failed_login_attempts = 0
                WHERE id = ?
            """, (user_id,))
        
        # Registrar actividad
        admin_id = session.get('user_id')
        activity_type = "Cuenta Bloqueada" if account_locked else "Cuenta Desbloqueada"
        cursor.execute("""
            INSERT INTO user_activity_log (user_id, activity_type, description, ip_address)
            VALUES (?, ?, ?, ?)
        """, (user_id, activity_type, f"Acción realizada por administrador (ID: {admin_id})", request.remote_addr))
        
        conn.commit()
        
        message = "Empleado bloqueado exitosamente" if account_locked else "Empleado desbloqueado exitosamente"
        return jsonify({'success': True, 'message': message})
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})
    finally:
        if conn:
            conn.close()

@admin_bp.route('/delete-employee', methods=['POST'])
@role_required(['admin'])
def delete_employee():
    """Eliminar un empleado"""
    try:
        employee_id = request.form.get('employeeId')
        
        if not employee_id:
            flash("ID de empleado no proporcionado", "danger")
            return redirect(url_for('admin.employees'))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Obtener el ID de usuario asociado al empleado
        cursor.execute("SELECT id FROM usuarios WHERE IDEmpleado = ?", (employee_id,))
        user_result = cursor.fetchone()
        
        # Eliminar registros de actividad si existe un usuario
        if user_result:
            user_id = user_result[0]
            cursor.execute("DELETE FROM user_activity_log WHERE user_id = ?", (user_id,))
            
            # Eliminar usuario
            cursor.execute("DELETE FROM usuarios WHERE id = ?", (user_id,))
        
        # Eliminar empleado
        cursor.execute("DELETE FROM Empleado WHERE IDEmpleado = ?", (employee_id,))
        
        conn.commit()
        
        flash("Empleado eliminado exitosamente", "success")
        return redirect(url_for('admin.employees'))
    
    except Exception as e:
        flash(f"Error al eliminar empleado: {str(e)}", "danger")
        return redirect(url_for('admin.employees'))
    finally:
        if conn:
            conn.close()