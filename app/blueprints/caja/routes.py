from flask import render_template, request, jsonify, session, redirect, url_for, flash
from app.blueprints.caja import caja_bp
from app.services.cash_service import CashService
from app.utils import login_required, role_required
from app.utils.db import get_db_connection

def get_empleado_id():
    user_id = session.get("user_id")
    if not user_id: return None
    conn = get_db_connection()
    try:
        emp = conn.execute("SELECT IDEmpleado FROM usuarios WHERE id = ?", (user_id,)).fetchone()
        if emp: return emp["IDEmpleado"]
    finally:
        conn.close()
    return None

@caja_bp.route('/')
@login_required
@role_required(['admin', 'gerente', 'vendedor'])
def index():
    empleado_id = get_empleado_id()
    if not empleado_id:
        flash("Tu usuario no tiene un perfil de empleado asignado para manejar caja.", "danger")
        return redirect(url_for('dashboard.index'))
        
    turno_abierto = CashService.verificar_turno_abierto(empleado_id)
    return render_template('caja/index.html', turno=turno_abierto)

@caja_bp.route('/abrir', methods=['POST'])
@login_required
@role_required(['admin', 'gerente', 'vendedor'])
def abrir_turno():
    try:
        monto = float(request.form.get("saldo_inicial", 0))
        empleado_id = get_empleado_id()
        if not empleado_id:
            return jsonify({"success": False, "message": "No cuentas con un perfil de empleado asociado."}), 400
            
        CashService.abrir_turno(empleado_id, monto)
        return jsonify({"success": True, "message": "Turno abierto exitosamente."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400

@caja_bp.route('/cerrar', methods=['POST'])
@login_required
@role_required(['admin', 'gerente', 'vendedor'])
def cerrar_turno():
    try:
        turno_id = int(request.form.get("turno_id"))
        saldo_real = float(request.form.get("saldo_real", 0))
        observaciones = request.form.get("observaciones", "")
        
        CashService.cerrar_turno(turno_id, saldo_real, observaciones)
        return jsonify({"success": True, "message": "Arqueo cerrado exitosamente."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400

@caja_bp.route('/gasto', methods=['POST'])
@login_required
@role_required(['admin', 'gerente'])
def registrar_gasto():
    try:
        monto = float(request.form.get("monto", 0))
        observacion = request.form.get("observacion", "")
        if monto <= 0:
            return jsonify({"success": False, "message": "Monto de gasto inválido"}), 400
            
        empleado_id = get_empleado_id()
        if not empleado_id:
            return jsonify({"success": False, "message": "No eres un empleado."}), 400
            
        CashService.registrar_flujo(empleado_id, monto, 'gasto')
        return jsonify({"success": True, "message": "Gasto registrado exitosamente."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400
