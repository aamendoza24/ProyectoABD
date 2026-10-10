from flask import Blueprint, render_template, request, flash, jsonify, redirect, url_for
from app.blueprints.inventario import inventario_bp
from app.services.producto_service import ProductoService
from app.repositories.producto_repository import ProductoRepository

@inventario_bp.route("/buscar_productos")
def buscar_productos():
    query = request.args.get("q", "")
    productos = ProductoRepository.buscar_productos_por_nombre(query)
    return jsonify(productos)

@inventario_bp.route("/stock")
def mostrar_stock():
    productos = ProductoRepository.obtener_stock_completo()
    categorias = ProductoRepository.obtener_categorias()
    return render_template("inventario/inventario.html", productos=productos, categorias=categorias)

@inventario_bp.route("/ver/<int:producto_id>")
def ver_detalle(producto_id):
    producto = ProductoRepository.obtener_producto_por_id(producto_id)
    return render_template("modals/modal_detalles.html", producto=producto)

@inventario_bp.route("/editar/<int:producto_id>")
def editar_producto(producto_id):
    producto = ProductoRepository.obtener_producto_por_id(producto_id)
    categorias = ProductoRepository.obtener_categorias()
    return render_template("modals/modal_editar.html", producto=producto, categorias=categorias)

@inventario_bp.route("/nuevo")
def nuevo_producto():
    categorias = ProductoRepository.obtener_categorias()
    return render_template("modals/modal_registrar.html", categorias=categorias)

@inventario_bp.route('/registrar-producto', methods=['POST'])
def registrar_producto():
    try:
        ProductoService.registrar_nuevo_producto(
            datos_formulario=request.form,
            archivo_imagen=request.files.get('imagen')
        )
        flash(f"Producto '{request.form.get('nombre')}' registrado exitosamente", "success")
    except ValueError as val_e:
        flash(str(val_e), "warning")
    except Exception as e:
        flash(f"Error al registrar el producto: {str(e)}", "danger")
        
    return redirect(url_for('inventario.mostrar_stock'))

@inventario_bp.route('/editar-producto/<int:producto_id>', methods=['POST'])
def editar_producto_bk(producto_id):
    try:
        ProductoService.editar_producto_existente(
            producto_id=producto_id,
            datos_formulario=request.form,
            archivo_imagen=request.files.get('imagenFile'),
            eliminar_imagen='eliminarImagen' in request.form
        )
        flash(f"Producto '{request.form.get('nombre')}' actualizado exitosamente", "success")
    except ValueError as val_e:
        flash(str(val_e), "warning")
    except Exception as e:
        flash(f"Error al actualizar el producto: {str(e)}", "danger")
        
    return redirect(url_for('inventario.mostrar_stock'))