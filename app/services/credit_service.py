from app.extensions import db
from app.repositories.credit_repository import CreditRepository
from datetime import datetime, timedelta

class CreditService:
    """Implementa la lógica de negocio para los créditos usando ORM en Inversión de Dependencias"""

    @staticmethod
    def crear_credito_desde_venta(venta_id, cliente_id, monto_total, dias_plazo=30):
        """Metodo orquestador llamado externamente por VentaService cuando hay crédito"""
        if monto_total <= 0:
            raise ValueError("El monto del crédito no puede ser menor o igual a cero.")
            
        fecha_limite = datetime.utcnow() + timedelta(days=dias_plazo)
        
        try:
            # Creación con Inyección de dependencia de Repository
            credito = CreditRepository.crear_credito(
                venta_id=venta_id,
                cliente_id=cliente_id,
                monto_deuda=monto_total,
                fecha_limite=fecha_limite
            )
            # NOTA: Quien llama a esto (VentaService) es responsable de hacer db.session.commit()
            return credito
        except Exception as e:
            raise Exception(f"No se pudo crear el crédito asociado a la venta: {str(e)}")

    @staticmethod
    def abonar_a_credito(credit_id, monto_abono, metodo_pago, referencia, empleado_id=None):
        """Registra un pago y actualiza dinámicamente si el crédito se canceló"""
        if monto_abono <= 0:
            raise ValueError("El abono debe ser mayor a cero.")
            
        credito = CreditRepository.obtener_credito_por_id(credit_id)
        if not credito:
            raise ValueError("Crédito no encontrado.")
            
        if credito.estado == 'pagado':
            raise ValueError("Este crédito ya está pagado por completo.")
            
        if monto_abono > credito.saldo_pendiente:
            raise ValueError(f"El abono rebasa el saldo pendiente de {credito.saldo_pendiente}")

        from app.services.cash_service import CashService
        
        if metodo_pago == 'efectivo' and empleado_id:
            if not CashService.verificar_turno_abierto(empleado_id):
                raise ValueError("Operación Denegada: Debes tener un turno de caja abierto para recibir efectivo.")

        try:
            abono = CreditRepository.registrar_abono(
                credit_id=credit_id,
                monto=monto_abono,
                metodo_pago=metodo_pago,
                referencia=referencia
            )
            
            # Evaluación In-Memory (Business Logic)
            if credito.saldo_pendiente <= 0.01: # Tolerancia decimal
                credito.estado = 'pagado'
                
            if metodo_pago == 'efectivo' and empleado_id:
                CashService.registrar_flujo(
                    empleado_id=empleado_id,
                    monto=monto_abono,
                    tipo='abono'
                )
                
            db.session.commit()
            return abono
        except Exception as e:
            db.session.rollback()
            raise Exception(str(e))

    @staticmethod
    def revisar_vencimientos():
        """Procesa y marca como vencidos los créditos activos con fecha sobrepasada.
        Ideal para lanzarse diario vía Scheduler."""
        activos = CreditRepository.obtener_todos_creditos_activos()
        
        modificados = 0
        for c in activos:
            if c.esta_vencido and c.estado != 'vencido':
                c.estado = 'vencido'
                modificados += 1
                
        if modificados > 0:
            db.session.commit()
            
        return modificados
