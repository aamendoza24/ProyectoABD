from app.extensions import db
from datetime import datetime

class CashTurn(db.Model):
    __tablename__ = 'cash_turns'
    
    id = db.Column(db.Integer, primary_key=True)
    empleado_id = db.Column(db.Integer, nullable=False)
    fecha_apertura = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_cierre = db.Column(db.DateTime, nullable=True)
    saldo_inicial = db.Column(db.Numeric(10, 2), nullable=False)
    ventas_contado = db.Column(db.Numeric(10, 2), default=0)
    abonos_recibidos = db.Column(db.Numeric(10, 2), default=0)
    gastos = db.Column(db.Numeric(10, 2), default=0)
    saldo_calculado = db.Column(db.Numeric(10, 2), default=0)
    saldo_real = db.Column(db.Numeric(10, 2), nullable=True)
    estado = db.Column(db.String(20), default='abierto') # abierto, cerrado
    observaciones = db.Column(db.Text, nullable=True)
