from flask import Blueprint, render_template, request, flash, jsonify, redirect, url_for, session
from datetime import datetime, timedelta, date
from app.utils.db import get_db_connection
from app.utils import login_required
from app.blueprints.compras import compras_bp


#compras_bp = Blueprint('compras', __name__, url_prefix='')


@compras_bp.route("/", methods=["GET", "POST"])
def index():
    # Este es el código que antes estaba en la función compras()
    db = get_db_connection()

    # Si la solicitud es de tipo POST (cuando se registra una compra)
    if request.method == "POST":
        data = request.get_json()
        proveedor_id = data.get("proveedor")
        productos = data.get("productos")
        sucursal_id = data.get("sucursal")
        
        if not productos:
            return jsonify({"message": "No se han agregado productos a la compra."}), 400
        
        try:
            # Empezar la transacción
            db.execute('BEGIN')
            
            # Insertar la compra en la tabla Compra
            fecha_actual = datetime.now().strftime("%Y-%m-%d")
            total_compra = 0
            
            # Calcular el total de la compra sumando los subtotales
            for producto in productos:
                cursor = db.cursor()
                cursor.execute("SELECT Precio FROM Producto WHERE IDProducto = ?", (producto['IDProducto'],))
                producto_data = cursor.fetchone()

                if not producto_data:
                    db.execute('ROLLBACK')
                    return jsonify({"message": f"Producto con ID {producto['IDProducto']} no encontrado."}), 404

                precio = float(producto['Precio'])  # Usar el precio enviado desde el frontend
                cantidad = int(producto['Cantidad'])
                subtotal = precio * cantidad
                total_compra += subtotal
                
                # Guardar el subtotal en el producto para usarlo después
                producto['subtotal'] = subtotal
            
            # Insertar en la tabla Compra
            cursor = db.cursor()
            cursor.execute("INSERT INTO Compra (Fecha, Total) VALUES (?, ?)", 
                          (fecha_actual, total_compra))
            
            # Obtener el ID de la compra recién insertada
            cursor.execute("SELECT last_insert_rowid()")
            compra_id = cursor.fetchone()[0]

            # Insertar en Detalle_Compra y actualizar stock
            for producto in productos:
                # Insertar detalle de compra con el subtotal calculado previamente
                cursor.execute(
                    "INSERT INTO Detalle_Compra (IDCompra, IDProducto, IDProveedor, IDSucursal, Cantidad, Subtotal) VALUES (?, ?, ?, ?, ?, ?)",
                    (compra_id, producto['IDProducto'], proveedor_id, sucursal_id, producto['Cantidad'], producto['subtotal'])
                )
                
                # Verificar si ya hay stock del producto en la sucursal
                cursor.execute("SELECT Cantidad FROM Stock_Sucursal WHERE IDProducto = ? AND IDSucursal = ?", 
                              (producto['IDProducto'], sucursal_id))
                stock_existente = cursor.fetchone()

                if stock_existente:
                    # Si existe, actualizar la cantidad
                    cursor.execute("UPDATE Stock_Sucursal SET Cantidad = Cantidad + ? WHERE IDProducto = ? AND IDSucursal = ?", 
                                  (producto['Cantidad'], producto['IDProducto'], sucursal_id))
                else:
                    # Si no existe, insertar nueva entrada en stock
                    cursor.execute("INSERT INTO Stock_Sucursal (IDSucursal, IDProducto, Cantidad) VALUES (?, ?, ?)", 
                                  (sucursal_id, producto['IDProducto'], producto['Cantidad']))

            # Confirmar los cambios en la base de datos
            db.commit()

            return jsonify({
                "message": "Compra registrada con éxito.",
                "compra_id": compra_id,
                "total": total_compra
            }), 200

        except Exception as e:
            # Si ocurre un error, revertir la transacción
            db.execute('ROLLBACK')
            return jsonify({"message": f"Error al registrar la compra: {str(e)}"}), 500
        finally:
            db.close()

    # Si la solicitud es de tipo GET (cuando se carga la página de compras)
    else:
        try:
            # Obtener datos para el formulario
            proveedores = db.execute("SELECT * FROM Proveedor ORDER BY Nombre").fetchall()
            productos = db.execute("SELECT * FROM Producto ORDER BY Nombre").fetchall()
            sucursales = db.execute("SELECT IDSucursal, Nombre FROM Sucursal ORDER BY Nombre").fetchall()
            
            # Consultar las compras realizadas con paginación
            page = request.args.get('page', 1, type=int)
            per_page = 10
            offset = (page - 1) * per_page
            
            # Obtener el total de compras para la paginación
            total_compras = db.execute("SELECT COUNT(DISTINCT c.IDCompra) FROM Compra c").fetchone()[0]
            
            # Consultar las compras con JOIN a las tablas relacionadas
            compras_realizadas = db.execute("""
                SELECT 
                    c.IDCompra, 
                    c.Fecha, 
                    c.Total, 
                    p.Nombre AS Proveedor,
                    s.Nombre AS Sucursal,
                    COUNT(DISTINCT d.IDProducto) AS NumProductos
                FROM Compra c
                JOIN Detalle_Compra d ON c.IDCompra = d.IDCompra
                JOIN Proveedor p ON d.IDProveedor = p.IDProveedor
                JOIN Sucursal s ON d.IDSucursal = s.IDSucursal
                GROUP BY c.IDCompra
                ORDER BY c.Fecha DESC, c.IDCompra DESC
                LIMIT ? OFFSET ?
            """, (per_page, offset)).fetchall()
            
            # Calcular el número total de páginas
            total_pages = (total_compras + per_page - 1) // per_page
            
            return render_template(
                "compras/compras.html", 
                proveedores=proveedores, 
                productos=productos, 
                sucursales=sucursales, 
                compras_realizadas=compras_realizadas,
                page=page,
                total_pages=total_pages,
                total_compras=total_compras
            )
        except Exception as e:
            flash(f"Error al cargar la página: {str(e)}", "danger")
            return render_template("error.html", error=str(e))
        finally:
            db.close()

@compras_bp.route("/actualizar_precio", methods=["POST"])
def actualizar_precio():
    data = request.get_json()
    id_producto = data["id_producto"]
    nuevo_precio = float(data["nuevo_precio"])

    try:
        conexion = get_db_connection()
        cursor = conexion.cursor()
        
        # Obtener el precio actual para registrar el cambio
        cursor.execute("SELECT Precio FROM Producto WHERE IDProducto = ?", (id_producto,))
        precio_anterior = cursor.fetchone()[0]
        
        # Actualizar el precio
        cursor.execute("UPDATE Producto SET Precio = ? WHERE IDProducto = ?", (nuevo_precio, id_producto))
        
        conexion.commit()
        conexion.close()
        
        return jsonify({
            "message": "Precio actualizado correctamente.",
            "precio_anterior": precio_anterior,
            "precio_nuevo": nuevo_precio
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@compras_bp.route("/buscar_productos")
def buscar_productos():
    query = request.args.get("q", "")
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT 
                p.IDProducto, 
                p.Nombre AS Producto, 
                p.Precio, 
                c.Nombre AS Categoria,
                COALESCE(SUM(ss.Cantidad), 0) AS StockTotal
            FROM Producto AS p
            JOIN Categoria AS c ON p.IDCategoria = c.IDCategoria 
            LEFT JOIN Stock_Sucursal AS ss ON p.IDProducto = ss.IDProducto
            WHERE p.Nombre LIKE ?
            GROUP BY p.IDProducto
            ORDER BY p.Nombre
        """, (f"%{query}%",))
        
        productos = [{
            "IDProducto": row["IDProducto"], 
            "Nombre": row["Producto"], 
            "Precio": row["Precio"], 
            "Categoria": row["Categoria"],
            "StockTotal": row["StockTotal"]
        } for row in cursor.fetchall()]
        
        return jsonify(productos)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@compras_bp.route("/detalle/<int:compra_id>")
def detalle(compra_id):
    try:
        db = get_db_connection()
        
        # Obtener información general de la compra
        compra = db.execute("""
            SELECT 
                c.IDCompra, 
                c.Fecha, 
                c.Total, 
                p.Nombre AS Proveedor,
                p.Telefono AS ProveedorTelefono,
                p.Email AS ProveedorEmail,
                s.Nombre AS Sucursal
            FROM Compra c
            JOIN Detalle_Compra d ON c.IDCompra = d.IDCompra
            JOIN Proveedor p ON d.IDProveedor = p.IDProveedor
            JOIN Sucursal s ON d.IDSucursal = s.IDSucursal
            WHERE c.IDCompra = ?
            LIMIT 1
        """, (compra_id,)).fetchone()
        
        if not compra:
            flash("Compra no encontrada", "danger")
            return redirect(url_for('compras.index'))
        
        # Obtener detalles de los productos
        detalles = db.execute("""
            SELECT 
                d.IDProducto,
                p.Nombre AS Producto,
                d.Cantidad,
                d.Subtotal,
                (d.Subtotal / d.Cantidad) AS PrecioUnitario,
                c.Nombre AS Categoria
            FROM Detalle_Compra d
            JOIN Producto p ON d.IDProducto = p.IDProducto
            JOIN Categoria c ON p.IDCategoria = c.IDCategoria
            WHERE d.IDCompra = ?
            ORDER BY p.Nombre
        """, (compra_id,)).fetchall()
        
        return render_template(
            "compras/detalle_compra.html",
            compra=compra,
            detalles=detalles
        )
    except Exception as e:
        flash(f"Error al cargar los detalles: {str(e)}", "danger")
        return redirect(url_for('compras.index'))
    finally:
        db.close()

@compras_bp.route("/reporte")
def reporte():
    try:
        db = get_db_connection()
        
        # Filtros
        fecha_inicio = request.args.get('fecha_inicio', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        fecha_fin = request.args.get('fecha_fin', datetime.now().strftime('%Y-%m-%d'))
        proveedor_id = request.args.get('proveedor_id', '')
        sucursal_id = request.args.get('sucursal_id', '')
        
        # Construir la consulta base para compras
        query = """
            SELECT 
                c.IDCompra, 
                c.Fecha, 
                c.Total, 
                p.Nombre AS Proveedor,
                s.Nombre AS Sucursal
            FROM Compra c
            JOIN Detalle_Compra d ON c.IDCompra = d.IDCompra
            JOIN Proveedor p ON d.IDProveedor = p.IDProveedor
            JOIN Sucursal s ON d.IDSucursal = s.IDSucursal
            WHERE c.Fecha BETWEEN ? AND ?
        """
        params = [fecha_inicio, fecha_fin]
        
        # Agregar filtros adicionales si se proporcionan
        if proveedor_id:
            query += " AND d.IDProveedor = ?"
            params.append(proveedor_id)
        
        if sucursal_id:
            query += " AND d.IDSucursal = ?"
            params.append(sucursal_id)
        
        query += " GROUP BY c.IDCompra ORDER BY c.Fecha DESC, c.IDCompra DESC"
        
        # Ejecutar la consulta
        compras = db.execute(query, params).fetchall()
        
        # Obtener estadísticas
        total_gastado = sum(compra['Total'] for compra in compras)
        num_compras = len(compras)
        promedio_compra = total_gastado / num_compras if num_compras > 0 else 0
        
        # Obtener proveedores y sucursales para los filtros
        proveedores = db.execute("SELECT IDProveedor, Nombre FROM Proveedor ORDER BY Nombre").fetchall()
        sucursales = db.execute("SELECT IDSucursal, Nombre FROM Sucursal ORDER BY Nombre").fetchall()
        categorias = db.execute("SELECT IDCategoria, Nombre FROM Categoria ORDER BY Nombre").fetchall()
        
        # Obtener datos para gráficos
        datos_por_proveedor = db.execute("""
            SELECT 
                p.Nombre AS Proveedor,
                SUM(c.Total) AS TotalGastado,
                COUNT(DISTINCT c.IDCompra) AS NumCompras
            FROM Compra c
            JOIN Detalle_Compra d ON c.IDCompra = d.IDCompra
            JOIN Proveedor p ON d.IDProveedor = p.IDProveedor
            WHERE c.Fecha BETWEEN ? AND ?
            GROUP BY p.IDProveedor
            ORDER BY TotalGastado DESC
        """, (fecha_inicio, fecha_fin)).fetchall()
        
        # Calcular compra promedio y porcentaje del total por proveedor
        for i, dato in enumerate(datos_por_proveedor):
            compra_promedio = dato['TotalGastado'] / dato['NumCompras'] if dato['NumCompras'] > 0 else 0
            porcentaje_total = (dato['TotalGastado'] / total_gastado * 100) if total_gastado > 0 else 0
            
            # SQLite no permite modificar directamente los resultados, así que creamos un nuevo diccionario
            datos_por_proveedor[i] = dict(dato)
            datos_por_proveedor[i]['CompraPromedio'] = compra_promedio
            datos_por_proveedor[i]['PorcentajeTotal'] = porcentaje_total
            datos_por_proveedor[i]['Tendencia'] = 0  # Valor por defecto, se calcularía con datos históricos
        
        datos_por_sucursal = db.execute("""
            SELECT 
                s.Nombre AS Sucursal,
                SUM(c.Total) AS TotalGastado
            FROM Compra c
            JOIN Detalle_Compra d ON c.IDCompra = d.IDCompra
            JOIN Sucursal s ON d.IDSucursal = s.IDSucursal
            WHERE c.Fecha BETWEEN ? AND ?
            GROUP BY s.IDSucursal
            ORDER BY TotalGastado DESC
        """, (fecha_inicio, fecha_fin)).fetchall()
        
        # Obtener top productos comprados
        top_productos = db.execute("""
            SELECT 
                p.Nombre AS Producto,
                SUM(d.Cantidad) AS TotalComprado,
                SUM(d.Subtotal) AS TotalGastado
            FROM Detalle_Compra d
            JOIN Producto p ON d.IDProducto = p.IDProducto
            JOIN Compra c ON d.IDCompra = c.IDCompra
            WHERE c.Fecha BETWEEN ? AND ?
            GROUP BY p.Nombre
            ORDER BY TotalGastado DESC
            LIMIT 5
        """, (fecha_inicio, fecha_fin)).fetchall()
        
        # Obtener análisis de productos
        productos_analisis = db.execute("""
            SELECT 
                p.Nombre AS Producto,
                cat.Nombre AS Categoria,
                SUM(d.Cantidad) AS UnidadesCompradas,
                (SUM(d.Subtotal) / SUM(d.Cantidad)) AS PrecioPromedio,
                SUM(d.Subtotal) AS TotalGastado
            FROM Detalle_Compra d
            JOIN Producto p ON d.IDProducto = p.IDProducto
            JOIN Compra c ON d.IDCompra = c.IDCompra
            JOIN Categoria cat ON p.IDCategoria = cat.IDCategoria
            WHERE c.Fecha BETWEEN ? AND ?
            GROUP BY p.Nombre, cat.Nombre
            ORDER BY TotalGastado DESC
        """, (fecha_inicio, fecha_fin)).fetchall()
        
        # Calcular porcentaje del total para cada producto
        for i, producto in enumerate(productos_analisis):
            porcentaje_total = (producto['TotalGastado'] / total_gastado * 100) if total_gastado > 0 else 0
            productos_analisis[i] = dict(producto)
            productos_analisis[i]['PorcentajeTotal'] = porcentaje_total
        
        # Obtener compras por día para gráfico de tendencia
        compras_por_dia = db.execute("""
            SELECT 
                date(c.Fecha) AS Fecha,
                SUM(c.Total) AS TotalCompras
            FROM Compra c
            WHERE c.Fecha BETWEEN ? AND ?
            GROUP BY date(c.Fecha)
            ORDER BY date(c.Fecha)
        """, (fecha_inicio, fecha_fin)).fetchall()
        
        # Calcular variación día a día
        compras_por_dia_con_variacion = []
        for i, dia in enumerate(compras_por_dia):
            variacion = 0
            if i > 0:
                variacion = dia['TotalCompras'] - compras_por_dia[i-1]['TotalCompras']
            compras_por_dia_con_variacion.append({
                'Fecha': dia['Fecha'],
                'TotalCompras': dia['TotalCompras'],
                'Variacion': variacion
            })
        
        # Obtener datos para gráficos de categorías
        categorias_query = db.execute("""
            SELECT 
                cat.Nombre AS Categoria,
                SUM(d.Subtotal) AS TotalGastado
            FROM Detalle_Compra d
            JOIN Producto p ON d.IDProducto = p.IDProducto
            JOIN Compra c ON d.IDCompra = c.IDCompra
            JOIN Categoria cat ON p.IDCategoria = cat.IDCategoria
            WHERE c.Fecha BETWEEN ? AND ?
            GROUP BY cat.Nombre
            ORDER BY TotalGastado DESC
        """, (fecha_inicio, fecha_fin)).fetchall()
        
        # Compras recientes
        compras_recientes = db.execute("""
            SELECT 
                c.IDCompra, 
                c.Fecha, 
                c.Total, 
                p.Nombre AS Proveedor
            FROM Compra c
            JOIN Detalle_Compra d ON c.IDCompra = d.IDCompra
            JOIN Proveedor p ON d.IDProveedor = p.IDProveedor
            GROUP BY c.IDCompra
            ORDER BY c.Fecha DESC, c.IDCompra DESC
            LIMIT 5
        """).fetchall()
        
        # Calcular total de productos comprados
        total_productos_comprados = db.execute("""
            SELECT SUM(d.Cantidad) 
            FROM Detalle_Compra d
            JOIN Compra c ON d.IDCompra = c.IDCompra
            WHERE c.Fecha BETWEEN ? AND ?
        """, (fecha_inicio, fecha_fin)).fetchone()[0] or 0
        
        # Calcular datos para comparación con período anterior
        fecha_inicio_dt = datetime.strptime(fecha_inicio, '%Y-%m-%d')
        fecha_fin_dt = datetime.strptime(fecha_fin, '%Y-%m-%d')
        dias_periodo = (fecha_fin_dt - fecha_inicio_dt).days + 1
        fecha_inicio_anterior = (fecha_inicio_dt - timedelta(days=dias_periodo)).strftime('%Y-%m-%d')
        fecha_fin_anterior = (fecha_fin_dt - timedelta(days=dias_periodo)).strftime('%Y-%m-%d')
        
        # Consulta para el período anterior
        query_anterior = """
            SELECT 
                SUM(c.Total) AS TotalGastado,
                COUNT(DISTINCT c.IDCompra) AS NumCompras
            FROM Compra c
            JOIN Detalle_Compra d ON c.IDCompra = d.IDCompra
            WHERE c.Fecha BETWEEN ? AND ?
        """
        params_anterior = [fecha_inicio_anterior, fecha_fin_anterior]
        
        if proveedor_id:
            query_anterior += " AND d.IDProveedor = ?"
            params_anterior.append(proveedor_id)
        
        if sucursal_id:
            query_anterior += " AND d.IDSucursal = ?"
            params_anterior.append(sucursal_id)
        
        datos_anterior = db.execute(query_anterior, params_anterior).fetchone()
        total_gastado_anterior = datos_anterior['TotalGastado'] if datos_anterior['TotalGastado'] else 0
        num_compras_anterior = datos_anterior['NumCompras'] if datos_anterior['NumCompras'] else 0
        promedio_compra_anterior = total_gastado_anterior / num_compras_anterior if num_compras_anterior > 0 else 0
        
        # Calcular porcentajes de crecimiento
        porcentaje_crecimiento_compras = ((total_gastado - total_gastado_anterior) / total_gastado_anterior * 100) if total_gastado_anterior > 0 else 0
        porcentaje_crecimiento_num_compras = ((num_compras - num_compras_anterior) / num_compras_anterior * 100) if num_compras_anterior > 0 else 0
        porcentaje_crecimiento_promedio = ((promedio_compra - promedio_compra_anterior) / promedio_compra_anterior * 100) if promedio_compra_anterior > 0 else 0
        
        # Calcular total de productos comprados en período anterior
        total_productos_anterior = db.execute("""
            SELECT SUM(d.Cantidad) 
            FROM Detalle_Compra d
            JOIN Compra c ON d.IDCompra = c.IDCompra
            WHERE c.Fecha BETWEEN ? AND ?
        """, (fecha_inicio_anterior, fecha_fin_anterior)).fetchone()[0] or 0
        
        porcentaje_crecimiento_productos = ((total_productos_comprados - total_productos_anterior) / total_productos_anterior * 100) if total_productos_anterior > 0 else 0
        
        # Preparar datos para gráficos en JavaScript
        fechas_compras = [dia['Fecha'] for dia in compras_por_dia]
        totales_compras = [float(dia['TotalCompras']) for dia in compras_por_dia]
        
        proveedores_labels = [dato['Proveedor'] for dato in datos_por_proveedor]
        proveedores_data = [float(dato['TotalGastado']) for dato in datos_por_proveedor]
        
        sucursales_labels = [dato['Sucursal'] for dato in datos_por_sucursal]
        sucursales_data = [float(dato['TotalGastado']) for dato in datos_por_sucursal]
        
        categorias_labels = [cat['Categoria'] for cat in categorias_query]
        categorias_data = [float(cat['TotalGastado']) for cat in categorias_query]
        
        top_productos_labels = [prod['Producto'] for prod in top_productos]
        top_productos_data = [float(prod['TotalGastado']) for prod in top_productos]
        
        return render_template(
            "compras/reporte_compras.html",
            compras=compras,
            total_gastado=total_gastado,
            num_compras=num_compras,
            promedio_compra=promedio_compra,
            proveedores=proveedores,
            sucursales=sucursales,
            categorias=categorias,
            proveedor_id=proveedor_id,
            sucursal_id=sucursal_id,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            datos_por_proveedor=datos_por_proveedor,
            datos_por_sucursal=datos_por_sucursal,
            top_productos=top_productos,
            productos_analisis=productos_analisis,
            compras_por_dia=compras_por_dia_con_variacion,
            compras_recientes=compras_recientes,
            total_productos_comprados=total_productos_comprados,
            porcentaje_crecimiento_compras=porcentaje_crecimiento_compras,
            porcentaje_crecimiento_num_compras=porcentaje_crecimiento_num_compras,
            porcentaje_crecimiento_promedio=porcentaje_crecimiento_promedio,
            porcentaje_crecimiento_productos=porcentaje_crecimiento_productos,
            fechas_compras=fechas_compras,
            totales_compras=totales_compras,
            proveedores_labels=proveedores_labels,
            proveedores_data=proveedores_data,
            sucursales_labels=sucursales_labels,
            sucursales_data=sucursales_data,
            categorias_labels=categorias_labels,
            categorias_data=categorias_data,
            top_productos_labels=top_productos_labels,
            top_productos_data=top_productos_data
        )
    except Exception as e:
        flash(f"Error al generar el reporte: {str(e)}", "danger")
        return redirect(url_for('compras.index'))
    finally:
        db.close()

# Ruta para exportar datos (opcional)
@compras_bp.route("/reporte/exportar", methods=['POST'])
def exportar_reporte():
    try:
        formato = request.form.get('formato', 'excel')
        tipo = request.form.get('tipo', 'completo')
        fecha_inicio = request.form.get('fecha_inicio')
        fecha_fin = request.form.get('fecha_fin')
        
        # Aquí implementarías la lógica para generar y devolver el archivo exportado
        # Por ahora, solo devolvemos un mensaje
        return jsonify({
            'success': True,
            'message': f'Exportación en formato {formato} del reporte {tipo} generada correctamente.'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error al exportar: {str(e)}'
        }), 500