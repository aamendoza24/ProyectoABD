from flask import Blueprint, render_template, request, flash, jsonify, redirect, url_for, current_app
from datetime import datetime, timedelta, date
from app.utils.db import get_db_connection
from app.utils import login_required
from app.blueprints.inventario import inventario_bp
import sqlite3
import requests
import base64
import os
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import uuid
from datetime import datetime
import json


#inventario_bp = Blueprint('inventario', __name__, url_prefix='')

IMGBB_API_KEY = '1a033715127541fff5dbf3fb2dd640d4'


@inventario_bp.route("/buscar_productos")
def buscar_productos():
    query = request.args.get("q", "")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT IDProducto, Nombre FROM Producto WHERE Nombre LIKE ?", (f"%{query}%",))
    productos = [{"IDProducto": row["IDProducto"], "Nombre": row["Nombre"]} for row in cursor.fetchall()]
    conn.close()
    return jsonify(productos)

#ruta para mostrar el stock de productos
@inventario_bp.route("/stock")
def mostrar_stock():
    conexion = get_db_connection()
    cursor = conexion.cursor()

    cursor.execute("""
        SELECT 
            p.IDProducto, 
            p.Nombre, 
            p.Precio AS precio_venta, 
            p.ImagenURL, 
            p.IDCategoria, 
            c.Nombre AS nombre_categoria, 
            COALESCE(s.Cantidad, 0) AS stock_total,
            COALESCE((
                SELECT (dc.Subtotal / CASE WHEN dc.Cantidad = 0 THEN 1 ELSE CAST(dc.Cantidad AS REAL) END)
                FROM Detalle_Compra dc
                JOIN Compra co ON dc.IDCompra = co.IDCompra
                WHERE dc.IDProducto = p.IDProducto
                ORDER BY co.Fecha DESC, dc.IDDetalleCompra DESC
                LIMIT 1
            ), 0.0) AS precio_compra
        FROM Producto AS p
        LEFT JOIN Categoria AS c ON p.IDCategoria = c.IDCategoria
        LEFT JOIN Stock_Sucursal AS s ON p.IDProducto = s.IDProducto AND s.IDSucursal = 1
    """)
    
    productos = cursor.fetchall()

    cursor.execute("SELECT IDCategoria, Nombre FROM Categoria")
    categorias = cursor.fetchall()

    conexion.close()
    
    return render_template("inventario/inventario.html", productos=productos, categorias=categorias)

def obtener_producto_por_id(producto_id):
    try:
        dbconection = get_db_connection()
        db = dbconection.cursor()
        db.execute(
            """SELECT p.IDProducto, p.Nombre, p.Precio, p.ImagenURL, 
                      p.IDCategoria, c.Nombre AS categoria_nombre,
                      COALESCE(s.Cantidad, 0) AS stock_total, 
                      p.Descripcion
               FROM Producto p 
               LEFT JOIN Categoria c ON p.IDCategoria = c.IDCategoria
               LEFT JOIN Stock_Sucursal s ON p.IDProducto = s.IDProducto AND s.IDSucursal = 1
               WHERE p.IDProducto = ?""",
            (producto_id,)
        )
        producto = db.fetchone()
        print(producto)
        return producto
    except Exception as e:
        print(f"Error al obtener producto: {e}")
        return None
    finally:
        db.close()
        dbconection.close()

#rutas para el renderizado de los modals 
@inventario_bp.route("/ver/<int:producto_id>")
def ver_detalle(producto_id):
    producto = obtener_producto_por_id(producto_id)
    print(producto)
    return render_template("modals/modal_detalles.html", producto=producto)

@inventario_bp.route("/editar/<int:producto_id>")
def editar_producto(producto_id):
    producto = obtener_producto_por_id(producto_id)
    return render_template("modals/modal_editar.html", producto=producto)

@inventario_bp.route("/nuevo")
def nuevo_producto():
    return render_template("modals/modal_registrar.html")

#rutas para procesar los formularios de los modals del inventario


#Funcion para validar si la extension de las imagenes es permitida 
def allowed_file(filename):
    """Verifica si la extensión del archivo es permitida"""
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

#funcion para subir la imagen a imgbb
def upload_to_imgbb(image_file):
    """
    Sube una imagen a ImgBB y devuelve la URL
    
    Args:
        image_file: Archivo de imagen del formulario
        
    Returns:
        dict: Diccionario con las URLs de la imagen o None si falla
    """
    try:
        # Obtener la API key de ImgBB
        api_key = IMGBB_API_KEY

            
        # Leer el archivo de imagen
        image_data = image_file.read()
        
        # Codificar la imagen en base64
        base64_image = base64.b64encode(image_data).decode('utf-8')
        
        # Preparar los datos para la solicitud
        payload = {
            'key': api_key,
            'image': base64_image,
            'name': f"{uuid.uuid4()}_{secure_filename(image_file.filename)}",
        }
        
        # Realizar la solicitud a la API de ImgBB
        response = requests.post('https://api.imgbb.com/1/upload', payload)
        
        # Verificar la respuesta
        if response.status_code == 200:
            result = response.json()
            if result['success']:
                # Devolver las URLs de la imagen
                return {
                    'url': result['data']['url'],
                    'delete_url': result['data']['delete_url'],
                    'thumbnail': result['data']['thumb']['url'],
                    'medium': result['data']['medium']['url'] if 'medium' in result['data'] else result['data']['url']
                }
        
        current_app.logger.error(f"Error al subir imagen a ImgBB: {response.text}")
        return None
        
    except Exception as e:
        current_app.logger.error(f"Error al subir imagen a ImgBB: {str(e)}")
        return None


#ruta para registrar el producto en la base de datos
@inventario_bp.route('/registrar-producto', methods=['POST'])
def registrar_producto():
    """Registrar un nuevo producto"""
    try:
        # Obtener datos del formulario
        nombre = request.form.get('nombre')
        precio = request.form.get('precio')
        categoria_id = request.form.get('categoria')
        stock = request.form.get('stock', 0)
        descripcion = request.form.get('descripcion', '')
        

        
        # Inicializar variables para la imagen
        imagen_url = None
        imagen_thumbnail = None
        imagen_data = None
        
        # Procesar imagen si se proporciona
        if 'imagen' in request.files and request.files['imagen'].filename:
            imagen_file = request.files['imagen']
            
            # Verificar si el archivo es válido
            if not allowed_file(imagen_file.filename):
                flash("Formato de imagen no permitido. Use JPG, PNG o GIF.", "danger")
                return redirect(url_for('inventario.mostrar_stock'))
            
            # Subir imagen a ImgBB
            imagen_result = upload_to_imgbb(imagen_file)
            
            if imagen_result:
                imagen_url = imagen_result['url']
                imagen_thumbnail = imagen_result['thumbnail']
                
                # Guardar información adicional de la imagen como JSON
                imagen_data = json.dumps({
                    'delete_url': imagen_result['delete_url'],
                    'medium': imagen_result['medium']
                })
            else:
                flash("No se pudo subir la imagen. El producto se guardará sin imagen.", "warning")
        
        # Conectar a la base de datos
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Insertar el producto en la base de datos
        cursor.execute("""
                INSERT INTO Producto (IDCategoria, Nombre, Descripcion, Precio, ImagenURL)
                VALUES (?, ?, ?, ?, ?)
            """, (categoria_id, nombre, descripcion, precio, imagen_url))
        
        # Obtener el ID del producto recién insertado
        producto_id = cursor.lastrowid
        
        # Registrar movimiento de inventario inicial si el stock es mayor que 0
        if int(stock) >= 0:
            cursor.execute("""
                INSERT INTO Stock_Sucursal (IDSucursal, IDProducto, Cantidad)
                VALUES (?, ?, ?)
            """, (1, producto_id, stock))
        
        conn.commit()
        
        flash(f"Producto '{nombre}' registrado exitosamente", "success")
        return redirect(url_for('inventario.mostrar_stock'))
    
    except Exception as e:
        flash(f"Error al registrar el producto: {str(e)}", "danger")
        return redirect(url_for('productos.mostrar_stock'))
    finally:
        if conn:
            conn.close()


# app/blueprints/productos/routes.py

@inventario_bp.route('/editar-producto/<int:producto_id>', methods=['POST'])
def editar_producto_bk(producto_id):
    """Editar un producto existente"""
    try:
        # Obtener datos del formulario
        nombre = request.form.get('nombre')
        precio = request.form.get('precio')
        categoria_id = request.form.get('categoria')
        descripcion = request.form.get('descripcion', '')
        
        # Validar datos obligatorios
        if not all([nombre, precio, categoria_id]):
            flash("Todos los campos obligatorios deben ser completados", "danger")
            return redirect(url_for('productos.index'))
        
        # Inicializar variables para la imagen
        imagen_url = None
        imagen_thumbnail = None
        imagen_data = None
        actualizar_imagen = False
        
        # Determinar qué hacer con la imagen
        if 'eliminarImagen' in request.form:
            # Si se marcó eliminar imagen, establecer URL a None
            imagen_url = None
            imagen_thumbnail = None
            imagen_data = None
            actualizar_imagen = True
        elif 'imagenFile' in request.files and request.files['imagenFile'].filename:
            # Procesar archivo de imagen
            imagen_file = request.files['imagenFile']
            
            # Verificar si el archivo es válido
            if not allowed_file(imagen_file.filename):
                flash("Formato de imagen no permitido. Use JPG, PNG o GIF.", "danger")
                return redirect(url_for('productos.index'))
            
            # Subir imagen a ImgBB
            imagen_result = upload_to_imgbb(imagen_file)
            
            if imagen_result:
                imagen_url = imagen_result['url']
                imagen_thumbnail = imagen_result['thumbnail']
                
                # Guardar información adicional de la imagen como JSON
                imagen_data = json.dumps({
                    'delete_url': imagen_result['delete_url'],
                    'medium': imagen_result['medium']
                })
                actualizar_imagen = True
            else:
                flash("No se pudo subir la imagen. El producto se actualizará sin cambiar la imagen.", "warning")
        
        # Conectar a la base de datos
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verificar que el producto existe
        cursor.execute("SELECT 1 FROM Producto WHERE IDProducto = ?", (producto_id,))
        if not cursor.fetchone():
            flash("Producto no encontrado", "danger")
            return redirect(url_for('inventario.mostrar_stock'))
        
        # Construir la consulta SQL para actualizar el producto
        update_fields = [
            "Nombre = ?", 
            "Precio = ?", 
            "IDCategoria = ?", 
            "Descripcion = ?"
        ]
        
        params = [
            nombre, 
            precio, 
            categoria_id, 
            descripcion
        ]
        
        # Añadir campos de imagen si se actualizaron
        if actualizar_imagen:
            update_fields.append(
                "ImagenURL = ?"
            )
            params.append(imagen_url)
        
        # Añadir el ID del producto al final de los parámetros
        params.append(producto_id)
        
        # Ejecutar la consulta de actualización
        cursor.execute(f"""
            UPDATE Producto 
            SET {', '.join(update_fields)}
            WHERE IDProducto = ?
        """, params)
        
        conn.commit()
        
        flash(f"Producto '{nombre}' actualizado exitosamente", "success")
        return redirect(url_for('inventario.mostrar_stock'))
    
    except Exception as e:
        flash(f"Error al actualizar el producto: {str(e)}", "danger")
        return redirect(url_for('inventario.mostrar_stock'))
    finally:
        if conn:
            conn.close()