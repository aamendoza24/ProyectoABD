from app.repositories.producto_repository import ProductoRepository
from app.services.image_service import ImageService
import json

class ProductoService:
    
    @staticmethod
    def registrar_nuevo_producto(datos_formulario, archivo_imagen=None):
        nombre = datos_formulario.get('nombre')
        precio = datos_formulario.get('precio')
        categoria_id = datos_formulario.get('categoria')
        stock = datos_formulario.get('stock', 0)
        descripcion = datos_formulario.get('descripcion', '')
        
        imagen_url = None
        
        if archivo_imagen and archivo_imagen.filename:
            if not ImageService.allowed_file(archivo_imagen.filename):
                raise ValueError("Formato de imagen no permitido. Use JPG, PNG o GIF.")
                
            imagen_result = ImageService.upload_to_imgbb(archivo_imagen)
            if imagen_result:
                imagen_url = imagen_result['url']
            else:
                raise Exception("No se pudo subir la imagen a ImgBB.")
                
        # Llamar al repositorio
        try:
            producto_id = ProductoRepository.crear_producto(
                categoria_id=categoria_id,
                nombre=nombre,
                descripcion=descripcion,
                precio=precio,
                imagen_url=imagen_url,
                stock_inicial=stock
            )
            return producto_id
        except Exception as e:
            raise Exception(f"Error al guardar producto en base de datos: {str(e)}")

    @staticmethod
    def editar_producto_existente(producto_id, datos_formulario, archivo_imagen=None, eliminar_imagen=False):
        nombre = datos_formulario.get('nombre')
        precio = datos_formulario.get('precio')
        categoria_id = datos_formulario.get('categoria')
        descripcion = datos_formulario.get('descripcion', '')
        
        if not all([nombre, precio, categoria_id]):
            raise ValueError("Todos los campos obligatorios deben ser completados")
            
        # Verificar existencia
        if not ProductoRepository.verificar_producto_existe(producto_id):
            raise ValueError("Producto no encontrado")
            
        imagen_url = None
        actualizar_imagen = False
        
        if eliminar_imagen:
            imagen_url = None
            actualizar_imagen = True
        elif archivo_imagen and archivo_imagen.filename:
            if not ImageService.allowed_file(archivo_imagen.filename):
                raise ValueError("Formato de imagen no permitido. Use JPG, PNG o GIF.")
                
            imagen_result = ImageService.upload_to_imgbb(archivo_imagen)
            if imagen_result:
                imagen_url = imagen_result['url']
                actualizar_imagen = True
            else:
                raise Exception("No se pudo subir la nueva imagen a ImgBB.")
                
        try:
            ProductoRepository.actualizar_producto(
                producto_id=producto_id,
                nombre=nombre,
                precio=precio,
                categoria_id=categoria_id,
                descripcion=descripcion,
                imagen_url=imagen_url,
                actualizar_imagen=actualizar_imagen
            )
        except Exception as e:
            raise Exception(f"Error al actualizar producto en base de datos: {str(e)}")
