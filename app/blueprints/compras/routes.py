from flask import Blueprint, render_template, request, flash, jsonify
from datetime import datetime, timedelta, date
from app.utils.db import get_db_connection
from app.utils import login_required
from app.blueprints.compras import compras_bp

#compras_bp = Blueprint('compras', __name__, url_prefix='')


#historial de compras
@compras_bp.route("/historial_compras")
def historial_compras():
    conexion = get_db_connection()
    cursor = conexion.cursor()

    cursor.execute("SELECT IDCompra, Fecha, Total FROM Compra")
    compras = [
        {"id": row[0], "fecha": row[1], "total": row[2]}
        for row in cursor.fetchall()
    ]

    conexion.close()
    return render_template("compras/historial_compras.html", compras=compras)


#Detalle de las compras
@compras_bp.route("/detalles_compra/<int:id_compra>", methods=["GET"])
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
@compras_bp.route("/realizar_compras", methods=["GET", "POST"])
def realizar_compras():
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
            "compras/compras.html", 
            proveedores=proveedores, 
            productos=productos, 
            sucursales=sucursales, 
            #compras_realizadas=compras_realizadas
        )
