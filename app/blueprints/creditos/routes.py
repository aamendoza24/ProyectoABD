from flask import render_template, request, jsonify, flash, session, redirect, url_for
from app.blueprints.creditos import creditos_bp
from app.services.credit_service import CreditService
from app.repositories.credit_repository import CreditRepository
from functools import wraps

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'role' not in session or session['role'] not in roles:
                flash('No tienes permiso para acceder a esta página.', 'danger')
                return redirect(url_for('dashboard.index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@creditos_bp.route('/')
@login_required
@role_required(['admin', 'gerente', 'vendedor'])
def index():
    # Primero forzamos la actualización de vencimientos (opcionalmente debería ir en un scheduler)
    CreditService.revisar_vencimientos()
    
    # Obtenemos la lista con SQLAlchemy ORM, no requiriendo convertirlos a Dict inmediatamente, 
    # pero a las templates les podemos mandar los objetos SQLAlchemy directo.
    creditos_orm = CreditRepository.obtener_todos_creditos_activos()
    
    # Formateamos para que la plantilla lo entienda fácil (similar a sqlite3.Row dict, pero usando propriedades ORM)
    creditos = []
    for c in creditos_orm:
        creditos.append({
            'id': c.id,
            'cliente': c.cliente.NombreCompleto,
            'monto_deuda': c.monto_deuda,
            'saldo_pendiente': c.saldo_pendiente,
            'fecha_limite': c.fecha_limite.strftime("%Y-%m-%d"),
            'estado': c.estado
        })
        
    return render_template('creditos/index.html', creditos=creditos)

@creditos_bp.route('/<int:credit_id>/detalles', methods=['GET'])
@login_required
def obtener_detalles(credit_id):
    c = CreditRepository.obtener_credito_por_id(credit_id)
    if not c:
        return jsonify({"success": False, "message": "Crédito no encontrado"}), 404
        
    pagos = []
    for pago in c.pagos:
        pagos.append({
            'monto': float(pago.monto),
            'fecha_pago': pago.fecha_pago.strftime("%Y-%m-%d %H:%M"),
            'metodo_pago': pago.metodo_pago,
            'referencia': pago.referencia or "N/A"
        })
        
    detalles = {
        'id': c.id,
        'venta_id': c.venta_id,
        'cliente_nombre': c.cliente.NombreCompleto,
        'cliente_telefono': c.cliente.Telefono,
        'fecha_creacion': c.fecha_creacion.strftime("%Y-%m-%d %H:%M"),
        'fecha_limite': c.fecha_limite.strftime("%Y-%m-%d"),
        'monto_deuda': float(c.monto_deuda),
        'saldo_pendiente': float(c.saldo_pendiente),
        'estado': c.estado,
        'pagos': pagos
    }
    
    return jsonify({"success": True, "detalles": detalles})

@creditos_bp.route('/<int:credit_id>/abonar', methods=['POST'])
@login_required
@role_required(['admin', 'gerente', 'vendedor'])
def abonar(credit_id):
    try:
        monto = float(request.form.get("monto", 0))
        metodo_pago = request.form.get("metodo_pago", "efectivo")
        referencia = request.form.get("referencia", "")
        
        empleado_id = None
        user_id = session.get("user_id")
        if user_id:
            from app.utils.db import get_db_connection
            conn = get_db_connection()
            try:
                emp = conn.execute("SELECT IDEmpleado FROM usuarios WHERE id = ?", (user_id,)).fetchone()
                if emp: empleado_id = emp["IDEmpleado"]
            finally:
                conn.close()

        CreditService.abonar_a_credito(credit_id, monto, metodo_pago, referencia, empleado_id)
        
        return jsonify({"success": True, "message": "Abono registrado exitosamente."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})
