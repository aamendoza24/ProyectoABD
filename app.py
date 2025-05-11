from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, make_response
from flask_session import Session #manejo de sesiones
from functools import wraps
import sqlite3
from datetime import datetime, timedelta, date
import bcrypt

app = Flask(__name__)

app.secret_key = 'tu_clave_secreta'  # Asegúrate de establecer una clave secreta

# Configure session to use filesystem (instead ofe signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

database_path = "library.db"  # Ruta al archivo de la base de datos SQLite

# Conexión con SQLite
#connection = sqlite3.connect(database_path, check_same_thread=False)  

#connection.row_factory = sqlite3.Row

def get_db_connection():
    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row
    return conn


#Decorador de ruta para el requerimiento de inicio de sesion
def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/1.1.x/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

#ruta para el cierre de sesion

@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('samples/login.html')  # Renderiza la página normalmente

    username = request.form.get("username")
    password = request.form.get("password")
    


    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, user, contrasena FROM usuarios WHERE user = ?", (username,))
        user = cursor.fetchone()
        if not user:
            return jsonify({"success": False, "message": "Usuario no encontrado."}), 400  # Código 400 para error

        if user:
            user_id = user["id"]
            stored_hashed_password = user["contrasena"]

            if isinstance(stored_hashed_password, str):
                stored_hashed_password = stored_hashed_password.encode('utf-8')

            if bcrypt.checkpw(password.encode('utf-8'), stored_hashed_password):
                session['user_id'] = user_id
                session['username'] = username
                return jsonify({"success": True, "message": "Inicio de sesión exitoso.", "redirect": "/"})

            return jsonify({"success": False, "message": "Contraseña incorrecta. Inténtalo de nuevo."})

        return jsonify({"success": False, "message": "Usuario no encontrado."})

    except sqlite3.Error as e:
        return jsonify({"success": False, "message": "Error al procesar la solicitud."})


#cierre de sesion
@app.route("/logout", methods=['POST'])
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")

# Ruta para la página principal
@app.route('/', methods=['GET', 'POST'])
def index():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.IDProducto, p.Nombre, p.Precio, p.ImagenURL, p.IDCategoria, c.Nombre, 
               s.Cantidad AS stock_total
        FROM Producto AS p
        JOIN Categoria AS c ON p.IDCategoria = c.IDCategoria
        JOIN Stock_Sucursal AS s ON p.IDProducto = s.IDProducto
        WHERE s.IDSucursal = 1
    """)
    
    productos = cursor.fetchall()

    # Lista para productos con stock bajo
    productos_bajo_stock = []

    for producto in productos:
        id_producto, nombre, precio, imagen, id_categoria, categoria_nombre, stock = producto
        if stock < 10:
            productos_bajo_stock.append(f"{nombre} ({stock} unidades)")

    # Si hay productos con bajo stock, mostrar un solo mensaje flash
    if productos_bajo_stock:
        mensaje = "⚠️ Los siguientes productos tienen bajo stock:\n" + ", ".join(productos_bajo_stock)
        flash(mensaje, "warning")

    return render_template("index.html", productos=productos)

#ruta para mostrar los productos en el apartado de venta
@app.route('/catalogo')
def catalogo():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""SELECT Producto.IDProducto, Nombre, Precio, ImagenURL, 
                        IDCategoria, Stock_Sucursal.Cantidad FROM Producto
                   JOIN Stock_Sucursal ON Producto.IDProducto = Stock_Sucursal.IDProducto
                   Where Stock_Sucursal.IDSucursal = 1""")
    productos = cursor.fetchall()
    cursor.execute("SELECT IDCategoria, Nombre FROM Categoria")
    categorias = cursor.fetchall()
    print(productos)
    print(categorias)

    return render_template("realizar_venta.html", productos=productos, categorias=categorias)


#ruta para el boton de annadir productos al carrito
@app.route("/agregar_carrito", methods=["POST"])
def agregar_al_carrito():
    if "carrito" not in session:
        session["carrito"] = []

    data = request.get_json()
    if not data:
        return jsonify({"error": "Solicitud incorrecta, formato JSON requerido"}), 400  # Evita errores si la solicitud está mal enviada

    id_producto = data.get("id")
    nombre = data.get("nombre")
    precio = float(data.get("precio", 0))

    carrito = session["carrito"]

    # Verificar si el producto ya está en el carrito
    for item in carrito:
        if item["id"] == id_producto:
            item["cantidad"] += 1
            break
    else:
        carrito.append({"id": id_producto, "nombre": nombre, "precio": precio, "cantidad": 1})

    session["carrito"] = carrito
    session.modified = True  # Asegura que Flask guarde los cambios en la sesión

    return jsonify({"success": True, "message": "Producto agregado al carrito!"})


#ruta en donde se podra visualizar el carrito y finalizar las ventas
@app.route("/carrito")
def ver_carrito():
    carrito = session.get("carrito", [])  # Obtener el carrito de la sesión
    total_carrito = sum(item["precio"] * item["cantidad"] for item in carrito) if carrito else 0

    return render_template("carrito.html", carrito=carrito, total_carrito=round(total_carrito, 2))

#ruta para actualizar las cantidades del carrito
@app.route("/actualizar_carrito", methods=["POST"])
def actualizar_carrito():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No se enviaron datos"}), 400

        id_producto = data.get("id")
        nueva_cantidad = data.get("cantidad")

        if not id_producto or not nueva_cantidad:
            return jsonify({"error": "ID o cantidad faltante"}), 400

        # Asegurar que la cantidad es un número entero válido
        try:
            nueva_cantidad = int(nueva_cantidad)
            if nueva_cantidad < 1:
                return jsonify({"error": "Cantidad no puede ser menor a 1"}), 400
        except ValueError:
            return jsonify({"error": "Cantidad no válida"}), 400

        # Verificar si el carrito existe en la sesión
        if "carrito" not in session:
            return jsonify({"error": "Carrito vacío"}), 400

        # Buscar el producto en el carrito
        for item in session["carrito"]:
            if item["id"] == id_producto:
                item["cantidad"] = nueva_cantidad
                session.modified = True
                return jsonify({"nuevo_total": round(item["precio"] * item["cantidad"], 2)})

        return jsonify({"error": "Producto no encontrado en el carrito"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500



#eliminar productos del carrito
@app.route("/eliminar_carrito", methods=["POST"])
def eliminar_carrito():
    data = request.get_json()
    id_producto = data.get("id")

    session["carrito"] = [item for item in session["carrito"] if item["id"] != id_producto]
    session.modified = True

    carrito_vacio = len(session["carrito"]) == 0
    return jsonify({"message": "Producto eliminado", "carrito_vacio": carrito_vacio})

#ruta para finalizar venta y agregar toda la informacion necesaria a la base de datos
@app.route("/finalizar_venta", methods=["POST"])
def finalizar_venta():
    if "carrito" not in session or not session["carrito"]:
        return jsonify({"error": "El carrito está vacío"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # Insertar la venta en la base de datos
    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO Venta (Fecha, Total) VALUES (?, ?)", (fecha_actual, sum(item["precio"] * item["cantidad"] for item in session["carrito"])))
    id_venta = cursor.lastrowid  # Obtener el ID de la venta recién insertada

    # Insertar los productos vendidos
    for item in session["carrito"]:
        cursor.execute("INSERT INTO Detalle_Venta (IDVenta, IDProducto, Cantidad, PrecioUnitario) VALUES (?, ?, ?, ?)",
                       (id_venta, item["id"], item["cantidad"], item["precio"]))

        #Actualizar el stock del producto
        cursor.execute("UPDATE Stock_Sucursal SET Cantidad = Cantidad - ? WHERE IDProducto = ?", (item["cantidad"], item["id"]))

    conn.commit()
    conn.close()

    # Vaciar el carrito después de la compra
    session["carrito"] = []
    session.modified = True

    return jsonify({"success": True, "message": "Venta finalizada correctamente!"})


@app.route("/guardar_venta", methods=["POST"])
def guardar_venta():
    data = request.get_json()

    productos = data.get("carrito", [])
    total = data.get("total")
    descuento = data.get("descuento", 0)
    tipo_pago = data.get("tipo_pago")
    cliente_nombre = data.get("cliente_nombre")
    cliente_id = data.get("cliente_id")
    cambio = data.get("cambio", 0)
    nota = data.get("nota", "")
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        db = get_db_connection()
        cursor = db.cursor()

        # Insertar la venta
        cursor.execute("""
            INSERT INTO Venta (Fecha, Total)
            VALUES (?, ?)
        """, (fecha, total))
        venta_id = cursor.lastrowid

        # Insertar los productos vendidos
        print(productos)
        for producto in productos:
            print("Producto insertado ", producto)
            cursor.execute("""
                INSERT INTO Detalle_Venta (IDVenta, IDProducto, Cantidad, PrecioUnitario, Subtotal)
                VALUES (?, ?, ?, ?, ?)
            """, (venta_id, producto["id"], producto["cantidad"], producto["precio"], producto["cantidad"] * producto["precio"] ))


            #Actualizacion del stock de productos
            cursor.execute("UPDATE Stock_Sucursal SET Cantidad = Cantidad - ? WHERE IDProducto = ?", (item["cantidad"], item["id"]))


        db.commit()
        return jsonify({"success": True, "mensaje": "Venta guardada exitosamente"}), 200

    except Exception as e:
        print("Error:", e)
        return jsonify({"error": "No se pudo guardar la venta"}), 500


def obtener_ventas(filtro):
    conexion = get_db_connection()

    cursor = conexion.cursor()

    if filtro == "hoy":
        fecha_limite = date.today() 
        cursor.execute("SELECT IDVenta, Fecha, Total FROM Venta WHERE DATE(Fecha) = ?", (fecha_limite,))
    elif filtro == "semana":
        fecha_limite = datetime.now() - timedelta(days=7)
        cursor.execute("SELECT IDVenta, Fecha, Total FROM Venta WHERE Fecha >= ?", (fecha_limite,))
    elif filtro == "mes":
        fecha_limite = datetime.now() - timedelta(days=30)
        cursor.execute("SELECT IDVenta, Fecha, Total FROM Venta WHERE Fecha >= ?", (fecha_limite,))
    else:
        cursor.execute("SELECT IDVenta, Fecha, Total FROM Venta")

    ventas = [{"id": row[0], "fecha": row[1], "total": row[2]} for row in cursor.fetchall()]
    conexion.close()
    return ventas

@app.route("/ventas", methods=["GET", "POST"])
def ventas():
    filtro = request.json["filtro"] if request.method == "POST" else "todas"
    ventas = obtener_ventas(filtro)

    if request.method == "POST":
        return jsonify({"ventas": ventas})

    return render_template("ventas.html", ventas=ventas)


#Ruta que retorna todos los detalles de la venta
@app.route("/detalles_venta/<int:id_venta>", methods=["GET"])
def detalles_venta(id_venta):
    conexion = get_db_connection()
    cursor = conexion.cursor()

    # Obtener información de la venta
    cursor.execute("""
        SELECT v.IDVenta, v.Fecha, v.Total, COALESCE(c.NombreCompleto, 'Cliente General') as Cliente, 
               COALESCE(v.MetodoPago, 'efectivo') as MetodoPago, COALESCE(v.Descuento, 0) as Descuento
        FROM Venta v
        LEFT JOIN Cliente c ON v.IDCliente = c.IDCliente
        WHERE v.IDVenta = ?
    """, (id_venta,))
    
    venta_row = cursor.fetchone()
    
    if not venta_row:
        conexion.close()
        return jsonify({"error": "Venta no encontrada"}), 404
    
    venta = {
        "id": venta_row[0],
        "fecha": venta_row[1],
        "total": venta_row[2],
        "cliente": venta_row[3],
        "metodo_pago": venta_row[4],
        "descuento": venta_row[5]
    }

    # Obtener detalles de la venta
    cursor.execute("""
        SELECT Producto.Nombre, Detalle_Venta.Cantidad, Detalle_Venta.PrecioUnitario
        FROM Detalle_Venta
        JOIN Producto ON Detalle_Venta.IDProducto = Producto.IDProducto
        WHERE Detalle_Venta.IDVenta = ?
    """, (id_venta,))

    detalles = [
        {"nombre": row[0], "cantidad": row[1], "precio_unitario": row[2]}
        for row in cursor.fetchall()
    ]
    
    conexion.close()
    return jsonify({"venta": venta, "detalles": detalles})



#historial de compras
@app.route("/historial_compras")
def historial_compras():
    conexion = get_db_connection()
    cursor = conexion.cursor()

    cursor.execute("SELECT IDCompra, Fecha, Total FROM Compra")
    compras = [
        {"id": row[0], "fecha": row[1], "total": row[2]}
        for row in cursor.fetchall()
    ]

    conexion.close()
    return render_template("historial_compras.html", compras=compras)


#Detalle de las compras
@app.route("/detalles_compra/<int:id_compra>", methods=["GET"])
def detalles_compra(id_compra):
    conexion = get_db_connection()
    cursor = conexion.cursor()

    cursor.execute("""
            SELECT  c.Fecha, pr.Nombre AS Proveedor, p.Nombre AS Producto,d.Cantidad,s.Nombre AS Sucursal,  c.Total
            FROM Compra c
            JOIN Detalle_Compra d ON c.IDCompra = d.IDCompra
            JOIN Producto p ON d.IDProducto = p.IDProducto
            JOIN Proveedor pr ON d.IDProveedor = pr.IDProveedor
            JOIN Sucursal s ON d.IDSucursal = s.IDSucursal
            WHERE d.IDCompra = ?
    """, (id_compra,))

    detalles = [
        {"Fecha": row[0], "Proveedor": row[1], "Producto": row[2],  "Cantidad": row[3], "Sucursal": row[4], "Total": row[5]}
        for row in cursor.fetchall()
    ]
    
    conexion.close()
    return jsonify({"detalles": detalles})

# Ruta para finalizar compra y agregar toda la información necesaria a la base de datos
@app.route("/compras", methods=["GET", "POST"])
def compras():
    db = get_db_connection()  # Usamos get_db_connection() para obtener la conexión
    
    # Si la solicitud es de tipo POST (cuando se registra una compra)
    if request.method == "POST":
        data = request.get_json()  # Esto obtiene los datos como JSON
        proveedor_id = data.get("proveedor")  # Extrae el ID del proveedor
        productos = data.get("productos")  # Extrae la lista de productos
        sucursal_id = data.get("sucursal")  # Obtener el ID de la sucursal desde el formulario
        if not productos:
            return jsonify({"message": "No se han agregado productos a la compra."}), 400
        
        try:
            # Empezar la transacción
            db.execute('BEGIN')  # Comienza una transacción explícita
            
            # Insertar la compra en la tabla Compra
            fecha_actual = datetime.now().strftime("%Y-%m-%d")
            total_compra = 0
            
            # Sumar los subtotales de los productos para calcular el total
            for producto in productos:
                # Obtener el precio del producto desde la base de datos
                cursor = db.cursor()
                cursor.execute("SELECT Precio FROM Producto WHERE IDProducto = ?", (producto['IDProducto'],))
                producto_data = cursor.fetchone()

                if not producto_data:
                    db.execute('ROLLBACK')  # Si no se encuentra un producto, revertir transacción
                    return jsonify({"message": f"Producto con ID {producto['IDProducto']} no encontrado."}), 404

                precio = producto_data[0]
                subtotal = precio * int(producto['Cantidad'])
                total_compra += subtotal
            
            # Insertar en la tabla Compra
            cursor.execute("INSERT INTO Compra (Fecha, Total) VALUES (?, ?)", (fecha_actual, total_compra))
            db.commit()

            # Consultar el ID de la última compra insertada
            cursor.execute("SELECT last_insert_rowid()")
            compra_id = cursor.lastrowid  # Obtiene el último ID insertado de manera más segura

            # Insertar en Detalle_Compra
            for producto in productos:
                # Insertar detalle de compra
                cursor.execute(
                    "INSERT INTO Detalle_Compra (IDCompra, IDProducto, IDProveedor, IDSucursal, Cantidad, Subtotal) VALUES (?, ?, ?, ?, ?, ?)",
                    (compra_id, producto['IDProducto'], proveedor_id, sucursal_id, producto['Cantidad'], subtotal)
                )

                
                # Verificar si ya hay stock del producto en la sucursal
                cursor.execute("SELECT Cantidad FROM Stock_Sucursal WHERE IDProducto = ?", (producto['IDProducto'],))
                stock_existente = cursor.fetchone()

                if stock_existente:
                    # Si existe, actualizar la cantidad
                    cursor.execute("UPDATE Stock_Sucursal SET Cantidad = Cantidad + ? WHERE IDProducto = ?", 
                                   (producto['Cantidad'], producto['IDProducto']))
                else:
                    # Si no existe, insertar nueva entrada en stock
                    cursor.execute("INSERT INTO Stock_Sucursal (IDSucursal,IDProducto, Cantidad) VALUES (?, ?, ?)", 
                                   (sucursal_id, producto['IDProducto'], producto['Cantidad']))

            # Confirmar los cambios en la base de datos
            db.commit()

            return jsonify({"message": "Compra registrada con éxito."}), 200

        except Exception as e:
            # Si ocurre un error, revertir la transacción
            db.execute('ROLLBACK')  # Revertir la transacción si hubo un error
            return jsonify({"message": f"Error al registrar la compra: {str(e)}"}), 500
    
    # Si la solicitud es de tipo GET (cuando se carga la página de compras)
    else:
        # Obtener datos para el formulario
        proveedores = db.execute("SELECT * FROM Proveedor").fetchall()
        productos = db.execute("SELECT * FROM Producto").fetchall()
        sucursales = db.execute("SELECT IDSucursal, Nombre FROM Sucursal").fetchall()
        
        # Consultar las compras realizadas
        #compras_realizadas = db.execute(""" 
            #SELECT c.IDCompra, c.Fecha, c.Total, p.Nombre AS Producto, pr.Nombre AS Proveedor, d.Cantidad, s.Nombre AS Sucursal
            #FROM Compra c
            #JOIN Detalle_Compra d ON c.IDCompra = d.IDCompra
            #JOIN Producto p ON d.IDProducto = p.IDProducto
            #JOIN Proveedor pr ON d.IDProveedor = pr.IDProveedor
            #JOIN Sucursal s ON d.IDSucursal = s.IDSucursal

        #""").fetchall()

        

        return render_template(
            "compras.html", 
            proveedores=proveedores, 
            productos=productos, 
            sucursales=sucursales, 
            #compras_realizadas=compras_realizadas
        )




@app.route("/buscar_productos")
def buscar_productos():
    query = request.args.get("q", "")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT IDProducto, Nombre FROM Producto WHERE Nombre LIKE ?", (f"%{query}%",))
    productos = [{"IDProducto": row["IDProducto"], "Nombre": row["Nombre"]} for row in cursor.fetchall()]
    conn.close()
    return jsonify(productos)

#ruta para mostrar el stock de productos
@app.route("/stock")
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
    
    return render_template("inventario.html", productos=productos, categorias=categorias)


@app.route("/reporte")
def reporte():
    db = get_db_connection()
    cursor = db.cursor()
    
    # Fecha actual para filtros predeterminados
    fecha_actual = datetime.now().strftime('%Y-%m-%d')
    
    # Agrupar ventas por fecha (solo fecha sin hora)
    cursor.execute("""
        SELECT DATE(Fecha) AS Fecha, SUM(Total) AS TotalVentas
        FROM Venta
        GROUP BY DATE(Fecha)
        ORDER BY DATE(Fecha)
    """)
    ventas = cursor.fetchall()

    # Preparar datos para gráficos
    fechas = [row["Fecha"] for row in reversed(ventas[-7:] if len(ventas) > 7 else ventas)]
    totales = [row["TotalVentas"] for row in reversed(ventas[-7:] if len(ventas) > 7 else ventas)]
    
    # Calcular crecimiento respecto al día anterior
    ventas_con_crecimiento = []
    prev_total = None
    for row in ventas:
        fecha = row["Fecha"]
        total = row["TotalVentas"]
        if prev_total is None:
            crecimiento = 0
        else:
            try:
                crecimiento = (total - prev_total)
            except ZeroDivisionError:
                crecimiento = 0
        ventas_con_crecimiento.append({
            "Fecha": fecha,
            "TotalVentas": total,
            "Crecimiento": round(crecimiento, 2)
        })
        prev_total = total

    # Gráfico: top 5 productos últimos 7 días
    cursor.execute("""
        SELECT P.Nombre, SUM(DV.Cantidad) as TotalVendido, SUM(DV.Cantidad * DV.PrecioUnitario) as TotalVentas
        FROM Detalle_Venta DV
        JOIN Producto P ON DV.IDProducto = P.IDProducto
        JOIN Venta V ON V.IDVenta = DV.IDVenta
        WHERE Fecha >= date('now', '-6 days')
        GROUP BY P.IDProducto
        ORDER BY TotalVendido DESC
        LIMIT 5
    """)
    top_productos = cursor.fetchall()
    
    nombres_productos = [p["Nombre"] for p in top_productos]
    cantidades_vendidas = [p["TotalVendido"] for p in top_productos]
    
    # Obtener ventas recientes
    cursor.execute("""
        SELECT V.IDVenta, V.Fecha, V.Total, COALESCE(C.NombreCompleto, 'Cliente General') as Cliente
        FROM Venta V
        LEFT JOIN Cliente C ON V.IDCliente = C.IDCliente
        ORDER BY V.Fecha DESC
        LIMIT 5
    """)
    ventas_recientes = cursor.fetchall()
    
    # Calcular KPIs para el dashboard
    
    # 1. Total ventas del período (último mes por defecto)
    cursor.execute("""
        SELECT SUM(Total) as TotalVentas
        FROM Venta
        WHERE Fecha >= date('now', '-30 days')
    """)
    result = cursor.fetchone()
    total_ventas_periodo = result["TotalVentas"] if result and result["TotalVentas"] else 0
    
    # 2. Total ventas del período anterior (para comparación)
    cursor.execute("""
        SELECT SUM(Total) as TotalVentas
        FROM Venta
        WHERE Fecha >= date('now', '-60 days') AND Fecha < date('now', '-30 days')
    """)
    result = cursor.fetchone()
    total_ventas_periodo_anterior = result["TotalVentas"] if result and result["TotalVentas"] else 0
    
    # 3. Calcular porcentaje de crecimiento
    if total_ventas_periodo_anterior > 0:
        porcentaje_crecimiento_ventas = round(((total_ventas_periodo - total_ventas_periodo_anterior) / total_ventas_periodo_anterior) * 100, 2)
    else:
        porcentaje_crecimiento_ventas = 100 if total_ventas_periodo > 0 else 0
    
    # 4. Ticket promedio
    cursor.execute("""
        SELECT AVG(Total) as TicketPromedio
        FROM Venta
        WHERE Fecha >= date('now', '-30 days')
    """)
    result = cursor.fetchone()
    ticket_promedio = result["TicketPromedio"] if result and result["TicketPromedio"] else 0
    
    # 5. Ticket promedio período anterior
    cursor.execute("""
        SELECT AVG(Total) as TicketPromedio
        FROM Venta
        WHERE Fecha >= date('now', '-60 days') AND Fecha < date('now', '-30 days')
    """)
    result = cursor.fetchone()
    ticket_promedio_anterior = result["TicketPromedio"] if result and result["TicketPromedio"] else 0
    
    # 6. Calcular porcentaje de crecimiento del ticket promedio
    if ticket_promedio_anterior > 0:
        porcentaje_crecimiento_ticket = round(((ticket_promedio - ticket_promedio_anterior) / ticket_promedio_anterior) * 100, 2)
    else:
        porcentaje_crecimiento_ticket = 100 if ticket_promedio > 0 else 0
    
    # 7. Total transacciones
    cursor.execute("""
        SELECT COUNT(*) as TotalTransacciones
        FROM Venta
        WHERE Fecha >= date('now', '-30 days')
    """)
    result = cursor.fetchone()
    total_transacciones = result["TotalTransacciones"] if result else 0
    
    # 8. Total transacciones período anterior
    cursor.execute("""
        SELECT COUNT(*) as TotalTransacciones
        FROM Venta
        WHERE Fecha >= date('now', '-60 days') AND Fecha < date('now', '-30 days')
    """)
    result = cursor.fetchone()
    total_transacciones_anterior = result["TotalTransacciones"] if result else 0
    
    # 9. Calcular porcentaje de crecimiento de transacciones
    if total_transacciones_anterior > 0:
        porcentaje_crecimiento_transacciones = round(((total_transacciones - total_transacciones_anterior) / total_transacciones_anterior) * 100, 2)
    else:
        porcentaje_crecimiento_transacciones = 100 if total_transacciones > 0 else 0
    
    # 10. Total productos vendidos
    cursor.execute("""
        SELECT SUM(Cantidad) as TotalProductos
        FROM Detalle_Venta DV
        JOIN Venta V ON V.IDVenta = DV.IDVenta
        WHERE V.Fecha >= date('now', '-30 days')
    """)
    result = cursor.fetchone()
    total_productos_vendidos = result["TotalProductos"] if result and result["TotalProductos"] else 0
    
    # 11. Total productos vendidos período anterior
    cursor.execute("""
        SELECT SUM(Cantidad) as TotalProductos
        FROM Detalle_Venta DV
        JOIN Venta V ON V.IDVenta = DV.IDVenta
        WHERE V.Fecha >= date('now', '-60 days') AND V.Fecha < date('now', '-30 days')
    """)
    result = cursor.fetchone()
    total_productos_vendidos_anterior = result["TotalProductos"] if result and result["TotalProductos"] else 0
    
    # 12. Calcular porcentaje de crecimiento de productos vendidos
    if total_productos_vendidos_anterior > 0:
        porcentaje_crecimiento_productos = round(((total_productos_vendidos - total_productos_vendidos_anterior) / total_productos_vendidos_anterior) * 100, 2)
    else:
        porcentaje_crecimiento_productos = 100 if total_productos_vendidos > 0 else 0
    
    # Obtener categorías para filtros
    cursor.execute("""
        SELECT IDCategoria, Nombre
        FROM Categoria
        ORDER BY Nombre
    """)
    categorias = cursor.fetchall()
    
    # Obtener rendimiento de productos (ejemplo)
    cursor.execute("""
        SELECT 
            P.Nombre, 
            C.Nombre as Categoria,
            SUM(DV.Cantidad) as UnidadesVendidas,
            AVG(DV.PrecioUnitario) as PrecioPromedio,
            SUM(DV.Cantidad * DV.PrecioUnitario) as TotalVentas
        FROM Detalle_Venta DV
        JOIN Producto P ON DV.IDProducto = P.IDProducto
        JOIN Categoria C ON P.IDCategoria = C.IDCategoria
        JOIN Venta V ON V.IDVenta = DV.IDVenta
        WHERE V.Fecha >= date('now', '-30 days')
        GROUP BY P.IDProducto
        ORDER BY TotalVentas DESC
        LIMIT 20
    """)
    productos_rendimiento_raw = cursor.fetchall()
    
    # Calcular porcentaje del total para cada producto
    total_ventas_productos = sum(p["TotalVentas"] for p in productos_rendimiento_raw)
    productos_rendimiento = []
    
    for producto in productos_rendimiento_raw:
        porcentaje = round((producto["TotalVentas"] / total_ventas_productos * 100), 2) if total_ventas_productos > 0 else 0
        productos_rendimiento.append({
            "Nombre": producto["Nombre"],
            "Categoria": producto["Categoria"],
            "UnidadesVendidas": producto["UnidadesVendidas"],
            "PrecioPromedio": round(producto["PrecioPromedio"], 2),
            "TotalVentas": round(producto["TotalVentas"], 2),
            "PorcentajeTotal": porcentaje
        })
    
    db.close()
    
    return render_template(
        "reporte_ventas.html",
        fecha_actual=fecha_actual,
        ventas_dia=ventas_con_crecimiento,
        fechas=fechas,
        totales=totales,
        nombres_productos=nombres_productos,
        cantidades_vendidas=cantidades_vendidas,
        top_productos=top_productos,
        ventas_recientes=ventas_recientes,
        total_ventas_periodo=round(total_ventas_periodo, 2),
        porcentaje_crecimiento_ventas=porcentaje_crecimiento_ventas,
        ticket_promedio=round(ticket_promedio, 2),
        porcentaje_crecimiento_ticket=porcentaje_crecimiento_ticket,
        total_transacciones=total_transacciones,
        porcentaje_crecimiento_transacciones=porcentaje_crecimiento_transacciones,
        total_productos_vendidos=total_productos_vendidos,
        porcentaje_crecimiento_productos=porcentaje_crecimiento_productos,
        categorias=categorias,
        productos_rendimiento=productos_rendimiento
    )

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
@app.route("/ver/<int:producto_id>")
def ver_detalle(producto_id):
    producto = obtener_producto_por_id(producto_id)
    print(producto)
    return render_template("modals/modal_detalles.html", producto=producto)

@app.route("/editar/<int:producto_id>")
def editar_producto(producto_id):
    producto = obtener_producto_por_id(producto_id)
    return render_template("modals/modal_editar.html", producto=producto)

@app.route("/nuevo")
def nuevo_producto():
    return render_template("modals/modal_registrar.html")

#rutas para procesar los formularios de los modals del inventario
@app.route("/registrar_producto", methods=["POST"])
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


@app.route("/editar_producto_ruta/<int:id>", methods=["POST"])
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


if __name__ == '__main__':
    app.run(debug=True)