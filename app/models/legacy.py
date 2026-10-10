from app.extensions import db

class Cliente(db.Model):
    """Mapeo parcial de la tabla Cliente existente"""
    __tablename__ = 'Cliente'
    __table_args__ = {'extend_existing': True}
    
    IDCliente = db.Column(db.Integer, primary_key=True)
    NombreCompleto = db.Column(db.String(100), nullable=False)
    Email = db.Column(db.String(100))
    Telefono = db.Column(db.String(20))

class Venta(db.Model):
    """Mapeo parcial de la tabla Venta existente"""
    __tablename__ = 'Venta'
    __table_args__ = {'extend_existing': True}
    
    IDVenta = db.Column(db.Integer, primary_key=True)
    Fecha = db.Column(db.DateTime)
    Total = db.Column(db.Numeric(10, 2), nullable=False)
    IDEmpleado = db.Column(db.Integer)
    IDCliente = db.Column(db.Integer, db.ForeignKey('Cliente.IDCliente'))
    IDSucursal = db.Column(db.Integer)
    MetodoPago = db.Column(db.String(50))
    Descuento = db.Column(db.Float)
    
    cliente = db.relationship('Cliente', backref='ventas')
