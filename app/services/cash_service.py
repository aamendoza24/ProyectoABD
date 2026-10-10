from app.extensions import db
from app.models.cash_turn import CashTurn
from datetime import datetime

class CashService:
    """Implementa la lógica del cuadre de caja diario (Arqueos)"""

    @staticmethod
    def abrir_turno(empleado_id, saldo_inicial):
        """Abre un turno para un cajero/vendedor, si no tiene ya uno abierto"""
        abierto = db.session.query(CashTurn).filter_by(
            empleado_id=empleado_id, estado='abierto'
        ).first()

        if abierto:
            raise ValueError("El empleado ya tiene un turno de caja abierto.")

        nuevo_turno = CashTurn(
            empleado_id=empleado_id,
            saldo_inicial=saldo_inicial
        )
        db.session.add(nuevo_turno)
        db.session.commit()
        return nuevo_turno

    @staticmethod
    def verificar_turno_abierto(empleado_id):
        """Retorna el turno abierto del empleado o None"""
        return db.session.query(CashTurn).filter_by(
            empleado_id=empleado_id, estado='abierto'
        ).first()

    @staticmethod
    def registrar_flujo(empleado_id, monto, tipo):
        """Registra una entrada ('venta', 'abono') o salida ('gasto') al turno abierto"""
        from decimal import Decimal
        monto_decimal = Decimal(str(monto))
        
        turno = db.session.query(CashTurn).filter_by(
            empleado_id=empleado_id, estado='abierto'
        ).first()

        if not turno:
            # Tolerancia: Dependiendo la regla de negocio, lanzar error o abrir automático en cero.
            raise ValueError("No hay un turno de caja abierto para contabilizar este flujo.")

        if tipo == 'venta':
            turno.ventas_contado += monto_decimal
        elif tipo == 'abono':
            turno.abonos_recibidos += monto_decimal
        elif tipo == 'gasto':
            turno.gastos += monto_decimal
            
        turno.saldo_calculado = (turno.saldo_inicial + turno.ventas_contado + turno.abonos_recibidos) - turno.gastos
        db.session.commit()
        return turno

    @staticmethod
    def cerrar_turno(turno_id, saldo_real, observaciones=None):
        """Realiza el arqueo final evaluando diferencias"""
        turno = db.session.query(CashTurn).filter_by(id=turno_id).first()
        if not turno:
            raise ValueError("Turno no encontrado")
            
        if turno.estado == 'cerrado':
            raise ValueError("El turno ya está cerrado")

        turno.fecha_cierre = datetime.utcnow()
        turno.saldo_real = saldo_real
        turno.estado = 'cerrado'
        turno.observaciones = observaciones
        
        # Opcional: Generar registro extra si hay faltante/sobrante para notificar
        diferencia = float(saldo_real) - float(turno.saldo_calculado)
        if diferencia != 0:
            if not turno.observaciones:
                turno.observaciones = ""
            turno.observaciones += f"\n[SISTEMA]: Se registró una diferencia de caja (Arqueo) de: {diferencia}"
            
        db.session.commit()
        return turno
