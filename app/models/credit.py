from app.extensions import db
from datetime import datetime

class Credit(db.Model):
    __tablename__ = 'credits'
    
    id = db.Column(db.Integer, primary_key=True)
    venta_id = db.Column(db.Integer, db.ForeignKey('Venta.IDVenta'), nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey('Cliente.IDCliente'), nullable=False)
    monto_deuda = db.Column(db.Numeric(10, 2), nullable=False)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_limite = db.Column(db.DateTime, nullable=False)
    estado = db.Column(db.String(20), default='activo') # activo, pagado, vencido
    
    # relationships
    venta = db.relationship('Venta', backref='credito', uselist=False)
    cliente = db.relationship('Cliente', backref='creditos')
    pagos = db.relationship('CreditPayment', backref='credito', cascade='all, delete-orphan')
    
    @property
    def saldo_pendiente(self):
        total_pagado = sum(float(pago.monto) for pago in self.pagos)
        return float(self.monto_deuda) - total_pagado

    @property
    def esta_vencido(self):
        return self.estado != 'pagado' and datetime.utcnow() > self.fecha_limite


class CreditPayment(db.Model):
    __tablename__ = 'credit_payments'
    
    id = db.Column(db.Integer, primary_key=True)
    credit_id = db.Column(db.Integer, db.ForeignKey('credits.id'), nullable=False)
    monto = db.Column(db.Numeric(10, 2), nullable=False)
    fecha_pago = db.Column(db.DateTime, default=datetime.utcnow)
    metodo_pago = db.Column(db.String(50))
    referencia = db.Column(db.String(100))
