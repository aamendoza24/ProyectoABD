from flask import Blueprint, render_template, request, flash, jsonify, send_file
from datetime import datetime, timedelta, date
from app.utils.db import get_db_connection
from app.utils import login_required, role_required
from app.blueprints.compras import compras_bp
import sqlite3
import pandas as pd
import io
import matplotlib.pyplot as plt
import seaborn as sns
import base64
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from app.utils import role_required

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


# #Detalle de las compras
# @compras_bp.route("/detalles_compra/<int:id_compra>", methods=["GET"])
# def detalles_compra(id_compra):
#     conexion = get_db_connection()
#     cursor = conexion.cursor()

#     cursor.execute("""
#             SELECT  c.Fecha, pr.Nombre AS Proveedor, p.Nombre AS Producto,d.Cantidad,s.Nombre AS Sucursal,  c.Total
#             FROM Compra c
#             JOIN Detalle_Compra d ON c.IDCompra = d.IDCompra
#             JOIN Producto p ON d.IDProducto = p.IDProducto
#             JOIN Proveedor pr ON d.IDProveedor = pr.IDProveedor
#             JOIN Sucursal s ON d.IDSucursal = s.IDSucursal
#             WHERE d.IDCompra = ?
#     """, (id_compra,))

#     detalles = [
#         {"Fecha": row[0], "Proveedor": row[1], "Producto": row[2],  "Cantidad": row[3], "Sucursal": row[4], "Total": row[5]}
#         for row in cursor.fetchall()
#     ]
    
#     conexion.close()
#     return jsonify({"detalles": detalles})

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



#endpoint sobre reportes de compras



@compras_bp.route('/compras')
@role_required(['admin', 'gerente'])
def compras():
    """Página principal de reportes de compras"""
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Obtener todas las sucursales para el filtro
        cursor.execute("SELECT IDSucursal, Nombre FROM Sucursal ORDER BY Nombre")
        sucursales = cursor.fetchall()
        
        # Obtener todos los proveedores para el filtro
        cursor.execute("SELECT IDProveedor, Nombre FROM Proveedor ORDER BY Nombre")
        proveedores = cursor.fetchall()
        
        # Obtener estadísticas generales de compras
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT c.IDCompra) as total_compras,
                COALESCE(SUM(c.Total), 0) as monto_total,
                COALESCE(AVG(c.Total), 0) as promedio_compra,
                COALESCE(MAX(c.Total), 0) as compra_maxima,
                COALESCE(MIN(c.Total), 0) as compra_minima,
                COUNT(DISTINCT dc.IDProveedor) as total_proveedores,
                COALESCE(SUM(dc.Cantidad), 0) as total_items
            FROM Compra c
            LEFT JOIN Detalle_Compra dc ON c.IDCompra = dc.IDCompra
        """)
        estadisticas = cursor.fetchone()
        
        # Obtener compras recientes (últimos 30 días)
        fecha_limite = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT 
                c.IDCompra,
                c.Fecha,
                c.Total,
                COUNT(DISTINCT dc.IDProducto) as num_productos,
                GROUP_CONCAT(DISTINCT p.Nombre) as proveedores,
                s.Nombre as sucursal
            FROM Compra c
            LEFT JOIN Detalle_Compra dc ON c.IDCompra = dc.IDCompra
            LEFT JOIN Proveedor p ON dc.IDProveedor = p.IDProveedor
            LEFT JOIN Sucursal s ON dc.IDSucursal = s.IDSucursal
            WHERE c.Fecha >= ?
            GROUP BY c.IDCompra
            ORDER BY c.Fecha DESC
            LIMIT 10
        """, (fecha_limite,))
        compras_recientes = cursor.fetchall()
        
        # Obtener datos para gráfico de compras por mes (últimos 6 meses)
        seis_meses_atras = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT 
                strftime('%Y-%m', c.Fecha) as mes,
                SUM(c.Total) as total
            FROM Compra c
            WHERE c.Fecha >= ?
            GROUP BY strftime('%Y-%m', c.Fecha)
            ORDER BY mes
        """, (seis_meses_atras,))
        datos_grafico_meses = cursor.fetchall()
        print(dict(datos_grafico_meses))
        
        # Obtener datos para gráfico de compras por proveedor (top 5)
        cursor.execute("""
            SELECT 
                p.Nombre as proveedor,
                SUM(dc.Subtotal) as total
            FROM Detalle_Compra dc
            JOIN Proveedor p ON dc.IDProveedor = p.IDProveedor
            JOIN Compra c ON dc.IDCompra = c.IDCompra
            WHERE c.Fecha >= ?
            GROUP BY p.IDProveedor
            ORDER BY total DESC
            LIMIT 5
        """, (seis_meses_atras,))
        datos_grafico_proveedores = cursor.fetchall()
        
        # Obtener datos para gráfico de compras por sucursal
        cursor.execute("""
            SELECT 
                s.Nombre as sucursal,
                SUM(dc.Subtotal) as total
            FROM Detalle_Compra dc
            JOIN Sucursal s ON dc.IDSucursal = s.IDSucursal
            JOIN Compra c ON dc.IDCompra = c.IDCompra
            WHERE c.Fecha >= ?
            GROUP BY s.IDSucursal
            ORDER BY total DESC
        """, (seis_meses_atras,))
        datos_grafico_sucursales = cursor.fetchall()
        
        # Obtener productos más comprados (top 10)
        cursor.execute("""
            SELECT 
                p.Nombre as producto,
                SUM(dc.Cantidad) as cantidad,
                SUM(dc.Subtotal) as total
            FROM Detalle_Compra dc
            JOIN Producto p ON dc.IDProducto = p.IDProducto
            JOIN Compra c ON dc.IDCompra = c.IDCompra
            WHERE c.Fecha >= ?
            GROUP BY p.IDProducto
            ORDER BY cantidad DESC
            LIMIT 10
        """, (seis_meses_atras,))
        productos_mas_comprados = cursor.fetchall()
        
        return render_template('compras/reporte_compras.html', 
                              sucursales=sucursales,
                              proveedores=proveedores,
                              estadisticas=estadisticas,
                              compras_recientes=compras_recientes,
                              datos_grafico_meses=datos_grafico_meses,
                              datos_grafico_proveedores=datos_grafico_proveedores,
                              datos_grafico_sucursales=datos_grafico_sucursales,
                              productos_mas_comprados=productos_mas_comprados)
    
    except Exception as e:
        return render_template('error.html', error=str(e))
    finally:
        if conn:
            conn.close()

@compras_bp.route('/api/compras/filtrar', methods=['GET'])
@role_required(['admin', 'gerente'])
def filtrar_compras():
    """API para filtrar compras según criterios"""
    try:
        # Obtener parámetros de filtro
        fecha_inicio = request.args.get('fecha_inicio', '')
        fecha_fin = request.args.get('fecha_fin', '')
        proveedor_id = request.args.get('proveedor_id', '')
        sucursal_id = request.args.get('sucursal_id', '')
        
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Construir la consulta base
        query = """
            SELECT 
                c.IDCompra,
                c.Fecha,
                c.Total,
                GROUP_CONCAT(DISTINCT p.Nombre) as proveedores,
                s.Nombre as sucursal,
                COUNT(DISTINCT dc.IDProducto) as num_productos
            FROM Compra c
            LEFT JOIN Detalle_Compra dc ON c.IDCompra = dc.IDCompra
            LEFT JOIN Proveedor p ON dc.IDProveedor = p.IDProveedor
            LEFT JOIN Sucursal s ON dc.IDSucursal = s.IDSucursal
            WHERE 1=1
        """
        params = []
        
        # Añadir filtros si se proporcionan
        if fecha_inicio:
            query += " AND c.Fecha >= ?"
            params.append(fecha_inicio)
        
        if fecha_fin:
            query += " AND c.Fecha <= ?"
            params.append(fecha_fin)
        
        if proveedor_id:
            query += " AND dc.IDProveedor = ?"
            params.append(proveedor_id)
        
        if sucursal_id:
            query += " AND dc.IDSucursal = ?"
            params.append(sucursal_id)
        
        # Agrupar y ordenar
        query += " GROUP BY c.IDCompra ORDER BY c.Fecha DESC"
        
        # Ejecutar la consulta
        cursor.execute(query, params)
        compras = [dict(row) for row in cursor.fetchall()]
        
        # Calcular totales
        total_compras = len(compras)
        monto_total = sum(compra['Total'] for compra in compras)
        
        return jsonify({
            'compras': compras,
            'total_compras': total_compras,
            'monto_total': monto_total
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

# @compras_bp.route('/api/compras/detalle/<int:compra_id>', methods=['GET'])
# @role_required(['admin', 'gerente'])
# def detalle_compra(compra_id):
#     """API para obtener el detalle de una compra específica"""
#     try:
#         conn = get_db_connection()
#         conn.row_factory = sqlite3.Row
#         cursor = conn.cursor()
        
#         # Obtener información general de la compra
#         cursor.execute("""
#             SELECT 
#                 c.IDCompra,
#                 c.Fecha,
#                 c.Total
#             FROM Compra c
#             WHERE c.IDCompra = ?
#         """, (compra_id,))
#         compra = dict(cursor.fetchone() or {})
        
#         if not compra:
#             return jsonify({'error': 'Compra no encontrada'}), 404
        
#         # Obtener detalles de la compra
#         cursor.execute("""
#             SELECT 
#                 dc.IDDetalleCompra,
#                 p.Nombre as producto,
#                 pr.Nombre as proveedor,
#                 s.Nombre as sucursal,
#                 dc.Cantidad,
#                 dc.Subtotal,
#                 (dc.Subtotal / dc.Cantidad) as precio_unitario
#             FROM Detalle_Compra dc
#             JOIN Producto p ON dc.IDProducto = p.IDProducto
#             JOIN Proveedor pr ON dc.IDProveedor = pr.IDProveedor
#             JOIN Sucursal s ON dc.IDSucursal = s.IDSucursal
#             WHERE dc.IDCompra = ?
#             ORDER BY p.Nombre
#         """, (compra_id,))
#         detalles = [dict(row) for row in cursor.fetchall()]
        
#         compra['detalles'] = detalles
        
#         return jsonify(compra)
    
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500
#     finally:
#         if conn:
#             conn.close()

@compras_bp.route('/exportar/compras', methods=['GET'])
@role_required(['admin', 'gerente'])
def exportar_compras():
    """Exportar reporte de compras a Excel (optimizado)"""
    try:
        # Obtener parámetros de filtro
        fecha_inicio = request.args.get('fecha_inicio', '')
        fecha_fin = request.args.get('fecha_fin', '')
        proveedor_id = request.args.get('proveedor_id', '')
        sucursal_id = request.args.get('sucursal_id', '')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Construir la consulta base para compras
        query_compras = """
            SELECT 
                c.IDCompra,
                c.Fecha,
                c.Total,
                GROUP_CONCAT(DISTINCT p.Nombre) as Proveedores,
                GROUP_CONCAT(DISTINCT s.Nombre) as Sucursales
            FROM Compra c
            LEFT JOIN Detalle_Compra dc ON c.IDCompra = dc.IDCompra
            LEFT JOIN Proveedor p ON dc.IDProveedor = p.IDProveedor
            LEFT JOIN Sucursal s ON dc.IDSucursal = s.IDSucursal
            WHERE 1=1
        """
        params = []
        
        # Añadir filtros si se proporcionan
        if fecha_inicio:
            query_compras += " AND c.Fecha >= ?"
            params.append(fecha_inicio)
        
        if fecha_fin:
            query_compras += " AND c.Fecha <= ?"
            params.append(fecha_fin)
        
        if proveedor_id:
            query_compras += " AND dc.IDProveedor = ?"
            params.append(proveedor_id)
        
        if sucursal_id:
            query_compras += " AND dc.IDSucursal = ?"
            params.append(sucursal_id)
        
        # Agrupar y ordenar
        query_compras += " GROUP BY c.IDCompra ORDER BY c.Fecha DESC"
        
        # Ejecutar la consulta de compras
        cursor.execute(query_compras, params)
        compras = cursor.fetchall()
        
        # Si no hay compras, devolver un mensaje
        if not compras:
            return "No hay datos para exportar con los filtros seleccionados", 404
        
        # Obtener IDs de compras para la consulta de detalles
        compra_ids = [str(compra[0]) for compra in compras]
        compra_ids_str = ','.join(compra_ids)
        
        # Consulta para detalles de compras
        query_detalles = f"""
            SELECT 
                dc.IDCompra,
                p.Nombre as Producto,
                pr.Nombre as Proveedor,
                s.Nombre as Sucursal,
                dc.Cantidad,
                dc.Subtotal,
                (dc.Subtotal / dc.Cantidad) as PrecioUnitario
            FROM Detalle_Compra dc
            JOIN Producto p ON dc.IDProducto = p.IDProducto
            JOIN Proveedor pr ON dc.IDProveedor = pr.IDProveedor
            JOIN Sucursal s ON dc.IDSucursal = s.IDSucursal
            WHERE dc.IDCompra IN ({compra_ids_str})
            ORDER BY dc.IDCompra, p.Nombre
        """
        
        # Ejecutar la consulta de detalles
        cursor.execute(query_detalles)
        detalles = cursor.fetchall()
        
        # Crear DataFrames de pandas
        df_compras = pd.DataFrame(compras, columns=['ID Compra', 'Fecha', 'Total', 'Proveedores', 'Sucursales'])
        df_detalles = pd.DataFrame(detalles, columns=['ID Compra', 'Producto', 'Proveedor', 'Sucursal', 'Cantidad', 'Subtotal', 'Precio Unitario'])
        
        # Crear un archivo Excel en memoria
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_compras.to_excel(writer, sheet_name='Compras', index=False)
            df_detalles.to_excel(writer, sheet_name='Detalles', index=False)
            
            # Obtener el objeto workbook y las hojas
            workbook = writer.book
            worksheet_compras = writer.sheets['Compras']
            worksheet_detalles = writer.sheets['Detalles']
            
            # Formato para moneda
            formato_moneda = workbook.add_format({'num_format': '$#,##0.00'})
            
            # Aplicar formato a columnas de moneda
            worksheet_compras.set_column('C:C', 12, formato_moneda)  # Total
            worksheet_detalles.set_column('F:G', 12, formato_moneda)  # Subtotal y Precio Unitario
            
            # Ajustar anchos de columna
            for worksheet in [worksheet_compras, worksheet_detalles]:
                for i, col in enumerate(worksheet.columns):
                    worksheet.set_column(i, i, 15)
        
        # Preparar el archivo para descarga
        output.seek(0)
        
        # Generar nombre de archivo con fecha actual
        fecha_actual = datetime.now().strftime('%Y%m%d')
        nombre_archivo = f"Reporte_Compras_{fecha_actual}.xlsx"
        
        return send_file(
            output,
            as_attachment=True,
            download_name=nombre_archivo,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    
    except Exception as e:
        return str(e), 500
    finally:
        if conn:
            conn.close()

@compras_bp.route('/api/compras/detalle/<int:compra_id>', methods=['GET'])
@role_required(['admin', 'gerente'])
def detalle_compra(compra_id):
    """API para obtener el detalle de una compra específica"""
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Obtener información general de la compra
        cursor.execute("""
            SELECT 
                c.IDCompra,
                c.Fecha,
                c.Total
            FROM Compra c
            WHERE c.IDCompra = ?
        """, (compra_id,))
        compra = dict(cursor.fetchone() or {})
        
        if not compra:
            return jsonify({'error': 'Compra no encontrada'}), 404
        
        # Obtener detalles de la compra
        cursor.execute("""
            SELECT 
                dc.IDDetalleCompra,
                p.Nombre as producto,
                p.IDProducto as codigo_producto,
                pr.Nombre as proveedor,
                pr.Telefono as telefono_proveedor,
                pr.DireccionCompleta as direccion_proveedor,
                s.Nombre as sucursal,
                s.Direccion as direccion_sucursal,
                dc.Cantidad,
                dc.Subtotal,
                (dc.Subtotal / dc.Cantidad) as precio_unitario
            FROM Detalle_Compra dc
            JOIN Producto p ON dc.IDProducto = p.IDProducto
            JOIN Proveedor pr ON dc.IDProveedor = pr.IDProveedor
            JOIN Sucursal s ON dc.IDSucursal = s.IDSucursal
            WHERE dc.IDCompra = ?
            ORDER BY p.Nombre
        """, (compra_id,))
        detalles = [dict(row) for row in cursor.fetchall()]
        
        compra['detalles'] = detalles
        
        return jsonify(compra)
    
    except Exception as e:
        import traceback
        print(f"Error al obtener detalle de compra: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500
    
    finally:
        if conn:
            conn.close()