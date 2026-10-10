from app.repositories.compra_repository import CompraRepository
from app.utils.db import get_db_connection
from datetime import datetime

class CompraService:
    """Maneja la lógica de negocio para el flujo de compras a proveedores"""

    @staticmethod
    def registrar_compra(datos_compra):
        """
        Orquesta la transacción completa de compra:
        1. Valida datos
        2. Registra cabecera de la compra.
        3. Registra detalles y actualiza inventario.
        4. Ejecuta Commit o Rollback automático.
        """
        proveedor_id = datos_compra.get('proveedor')
        sucursal_id = datos_compra.get('sucursal')
        productos = datos_compra.get('productos', [])
        fecha = datos_compra.get('fecha', datetime.now().strftime('%Y-%m-%d'))
        referencia = datos_compra.get('referencia', '')
        
        if not proveedor_id or not sucursal_id or not productos:
            raise ValueError('Faltan datos requeridos (proveedor, sucursal, productos)')

        total = sum(float(p['Cantidad']) * float(p['PrecioCompra']) for p in productos)

        db = get_db_connection()
        try:
            # Cabecera
            compra_id = CompraRepository.crear_compra_cabecera(db, fecha, total)
            
            # Detalles y actualización de stock
            for producto in productos:
                producto_id = producto['IDProducto']
                cantidad = float(producto['Cantidad'])
                precio_compra = float(producto['PrecioCompra'])
                subtotal = cantidad * precio_compra

                CompraRepository.guardar_detalle_compra(
                    db,
                    compra_id,
                    producto_id,
                    proveedor_id,
                    sucursal_id,
                    cantidad,
                    subtotal,
                    precio_compra,
                    referencia
                )

                CompraRepository.actualizar_o_insertar_stock(
                    db,
                    sucursal_id,
                    producto_id,
                    cantidad
                )
            
            db.commit()
            return {"success": True, "message": "Compra registrada correctamente", "compra_id": compra_id}
            
        except Exception as e:
            db.rollback()
            raise Exception(f"No se pudo guardar la compra: {str(e)}")
        finally:
            db.close()
