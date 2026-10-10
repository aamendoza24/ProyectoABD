from app.repositories.venta_repository import VentaRepository
from app.repositories.cliente_repository import ClienteRepository
from app.utils.db import get_db_connection
from datetime import datetime
import pytz

class VentaService:
    """Maneja la lógica de negocio para el flujo de ventas"""

    @staticmethod
    def procesar_y_guardar_venta(datos_carrito, empleado_id: int, sucursal_id: int = 1):
        """
        Orquesta la transacción completa de venta:
        1. Resuelve cliente.
        2. Registra cabecera de la venta.
        3. Registra detalles y descuenta inventario.
        4. Ejecuta Commit o Rollback automático.
        """
        productos = datos_carrito.get("carrito", [])
        total = datos_carrito.get("total")
        descuento = datos_carrito.get("descuento", 0)
        tipo_pago = datos_carrito.get("tipo_pago")
        
        cliente_id_input = datos_carrito.get("cliente_id")
        cliente_nombre = datos_carrito.get("cliente_nombre")
        cliente_telefono = datos_carrito.get("cliente_telefono")
        
        nicaragua_tz = pytz.timezone('America/Managua')
        fecha = datetime.now(nicaragua_tz).strftime("%Y-%m-%d %H:%M:%S")

        from app.services.cash_service import CashService

        # Pre-validación estricta de Arqueo
        prima_inicial = float(datos_carrito.get("dinero_recibido") or 0.0)
        es_flujo_efectivo = tipo_pago == 'efectivo' or (tipo_pago == 'credito' and prima_inicial > 0)

        if es_flujo_efectivo:
            if not CashService.verificar_turno_abierto(empleado_id):
                raise ValueError("Operación Denegada: Debes realizar la 'Apertura de Turno' en Módulo de Caja antes de recibir efectivo.")

        db = get_db_connection()
        try:
            # 1. Resolver el cliente
            cliente_id_final = None
            if cliente_id_input:
                cliente_id_final = cliente_id_input
            elif cliente_nombre and cliente_telefono:
                # Si se envían datos y no ID, se crea un nuevo cliente dentro de la transacción
                cliente_id_final = ClienteRepository.crear_cliente_con_conexion(
                    nombre=cliente_nombre, 
                    telefono=cliente_telefono, 
                    conexion=db
                )
            
            # 2. Registrar la cabecera
            id_venta = VentaRepository.crear_venta_cabecera(
                conexion=db,
                fecha=fecha,
                total=total,
                id_empleado=empleado_id,
                id_cliente=cliente_id_final,
                id_sucursal=sucursal_id,
                metodo_pago=tipo_pago,
                descuento=descuento
            )

            # 3. Registrar detalles y descontar stock
            for producto in productos:
                id_producto = producto["id"]
                cantidad = producto["cantidad"]
                precio = producto["precio"]
                subtotal = cantidad * precio

                VentaRepository.guardar_detalle_venta(
                    conexion=db,
                    id_venta=id_venta,
                    id_producto=id_producto,
                    cantidad=cantidad,
                    precio_unitario=precio,
                    subtotal=subtotal
                )

                VentaRepository.descontar_stock(
                    conexion=db,
                    id_producto=id_producto,
                    cantidad=cantidad,
                    id_sucursal=sucursal_id
                )

            # 4. Finalizar Transacción
            db.commit()

            # 5. Integración con Módulo de Créditos (SQLAlchemy ORM)
            # Como la capa Base VentaService corre en sqlite puro, generamos el Commitment primero,
            # y despachamos al CreditService que ya maneja su propia sesión ORM.
            from app.services.credit_service import CreditService
            from app.extensions import db as orm_db

            if tipo_pago == 'credito':
                if not cliente_id_final:
                    raise ValueError("Las ventas al crédito requieren obligatoriamente un Cliente registrado.")
                    
                dias_plazo = int(datos_carrito.get("dias_plazo") or 30)
                # Creamos el crédito llamando al módulo SQLAlchemy
                credito = CreditService.crear_credito_desde_venta(
                    venta_id=id_venta,
                    cliente_id=cliente_id_final,
                    monto_total=total,
                    dias_plazo=dias_plazo
                )
                
                # Procesar Dinero Recibido como Prima / Abono Inicial
                prima_inicial = float(datos_carrito.get("dinero_recibido") or 0.0)
                if prima_inicial > 0:
                    CreditService.abonar_a_credito(
                        credit_id=credito.id,
                        monto_abono=prima_inicial,
                        metodo_pago="efectivo",
                        referencia="Prima Inicial",
                        empleado_id=empleado_id
                    )
                    
                orm_db.session.commit()
                
            elif tipo_pago == 'efectivo':
                CashService.registrar_flujo(
                    empleado_id=empleado_id,
                    monto=total,
                    tipo='venta'
                )

            return {"success": True, "mensaje": "Venta guardada exitosamente"}

        except Exception as e:
            db.rollback()
            try:
                from app.extensions import db as orm_db
                orm_db.session.rollback()
            except Exception:
                pass
            print("Error en Servicio de Ventas:", e)
            raise e
        finally:
            db.close()
