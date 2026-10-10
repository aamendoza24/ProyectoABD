from app.extensions import db
from app.models.credit import Credit, CreditPayment
from datetime import datetime

class CreditRepository:
    """Maneja las operaciones de persistencia para el Módulo de Créditos"""

    @staticmethod
    def crear_credito(venta_id, cliente_id, monto_deuda, fecha_limite):
        credito = Credit(
            venta_id=venta_id,
            cliente_id=cliente_id,
            monto_deuda=monto_deuda,
            fecha_limite=fecha_limite,
            estado='activo'
        )
        db.session.add(credito)
        db.session.flush() # Para emitir el ID antes de comitear
        return credito

    @staticmethod
    def registrar_abono(credit_id, monto, metodo_pago, referencia=None):
        abono = CreditPayment(
            credit_id=credit_id,
            monto=monto,
            metodo_pago=metodo_pago,
            referencia=referencia
        )
        db.session.add(abono)
        db.session.flush()
        return abono

    @staticmethod
    def obtener_credito_por_id(credit_id):
        return db.session.query(Credit).filter_by(id=credit_id).first()

    @staticmethod
    def obtener_creditos_por_cliente(cliente_id):
        return db.session.query(Credit).filter_by(cliente_id=cliente_id).order_by(Credit.fecha_creacion.desc()).all()

    @staticmethod
    def obtener_todos_creditos_activos():
        return db.session.query(Credit).filter(Credit.estado != 'pagado').order_by(Credit.fecha_limite.asc()).all()

    @staticmethod
    def actualizar_estado(credit_id, estado):
        credito = db.session.query(Credit).filter_by(id=credit_id).first()
        if credito:
            credito.estado = estado
            db.session.flush()
            return True
        return False
