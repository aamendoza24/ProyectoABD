from flask import Blueprint, render_template, request, flash, jsonify, redirect
from datetime import datetime, timedelta, date
from app.utils.db import get_db_connection
from app.utils import login_required
from app.blueprints.inventario import inventario_bp

#inventario_bp = Blueprint('inventario', __name__, url_prefix='')


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
        SELECT p.IDProducto, p.Nombre, p.Precio, p.ImagenURL, p.IDCategoria, c.Nombre, 
               s.Cantidad AS stock_total
        FROM Producto AS p
        JOIN Categoria AS c ON p.IDCategoria = c.IDCategoria
        JOIN Stock_Sucursal AS s ON p.IDProducto = s.IDProducto
        WHERE s.IDSucursal = 1
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
@inventario_bp.route("/registrar_producto", methods=["POST"])
def registrar_producto():

    nombre = request.form["nombre"]
    precio = request.form["precio"]
    imagen = request.form["imagen"]
    categoria = request.form["categoria"]
    dbconexion = get_db_connection()
    db = dbconexion.cursor()
    db.execute("INSERT INTO productos (nombre, precio, imagen, categoria_id) VALUES (?, ?, ?, ?)",
               nombre, precio, imagen, categoria)
    db.commit()
    db.close()
    return redirect("/inventario")


@inventario_bp.route("/editar_producto_ruta/<int:id>", methods=["POST"])
def editar_producto_ruta(id):
    nombre = request.form["nombre"]
    precio = request.form["precio"]
    imagen = request.form["imagen"]
    categoria = request.form["categoria"]
    dbconexion = get_db_connection()
    db = dbconexion.cursor()
    db.execute("UPDATE productos SET nombre = ?, precio = ?, imagen = ?, categoria_id = ? WHERE id = ?",
               nombre, precio, imagen, categoria, id)
    db.commit()
    db.close()
    return redirect("/inventario")