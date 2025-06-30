document.addEventListener("DOMContentLoaded", function () {
    // Variables globales
    let carrito = [];
    let notificacionTimeout;
    let ventaActual = null; // Para almacenar los datos de la venta actual
    
    // Elementos DOM
    const carritoTable = document.getElementById("carrito");
    const totalSpan = document.getElementById("total");
    const buscarInput = document.getElementById("buscar");
    const filtroCategoria = document.getElementById("filtro-categoria");
    const productosContainer = document.getElementById("productos");
    const emptyCartRow = document.querySelector(".empty-cart");
    const noResultadosDiv = document.getElementById("no-resultados");
    const carritoTablaContainer = document.querySelector(".carrito-tabla-container");
    
    // Elementos del modal de pago
    const modalPago = new bootstrap.Modal(document.getElementById('modalPago'));
    const totalPagoInput = document.getElementById('totalPago');
    const dineroRecibidoInput = document.getElementById('dineroRecibido');
    const cambioInput = document.getElementById('cambio');
    const dineroRecibidoFeedback = document.getElementById('dineroRecibidoFeedback');
    const tipoPagoSelect = document.getElementById('tipoPago');
    
    // Botones
    const btnPagar = document.getElementById("btnPagar");
    const btnVaciarCarrito = document.getElementById("vaciarCarrito");
    const finalizarPagoBtn = document.getElementById('finalizarPago');
    
    // Inicializar carrito
    actualizarCarrito();
    
    // ===== FUNCIONES PRINCIPALES =====
    
    // Agregar productos al carrito
    productosContainer.addEventListener("click", function (e) {
        const botonAgregar = e.target.closest(".agregar-carrito");
        if (botonAgregar) {
            const id = botonAgregar.dataset.id;
            const nombre = botonAgregar.dataset.nombre;
            const precio = parseFloat(botonAgregar.dataset.precio);
            const stock = parseInt(botonAgregar.dataset.stock);
            
            const productoExistente = carrito.find(p => p.id === id);

            // Efecto visual en el botón
            botonAgregar.classList.add("shake");
            setTimeout(() => botonAgregar.classList.remove("shake"), 500);

            if (productoExistente) {
                if (productoExistente.cantidad < stock) {
                    productoExistente.cantidad++;
                    mostrarNotificacion(`Cantidad de "${nombre}" actualizada (${productoExistente.cantidad})`, "success");
                } else {
                    mostrarNotificacion(`No hay suficiente stock para "${nombre}"`, "warning");
                }
            } else {
                if (stock > 0) {
                    carrito.push({ id, nombre, precio, cantidad: 1 , stock});
                    mostrarNotificacion(`"${nombre}" agregado al carrito`, "success");
                } else {
                    mostrarNotificacion(`"${nombre}" está agotado`, "warning");
                }
            }

            actualizarCarrito();
        }
    });


    // Actualizar carrito
    function actualizarCarrito() {
        // Limpiar tabla
        while (carritoTable.firstChild) {
            carritoTable.removeChild(carritoTable.firstChild);
        }
        
        // Calcular total
        let total = 0;
        
        // Mostrar mensaje de carrito vacío si no hay productos
        if (carrito.length === 0) {
            const emptyRow = document.createElement("tr");
            emptyRow.className = "empty-cart";
            emptyRow.innerHTML = `
                <td colspan="4" class="text-center">
                    <div class="empty-cart-message">
                        <i class="fas fa-shopping-basket"></i>
                        <p>El carrito está vacío</p>
                    </div>
                </td>
            `;
            carritoTable.appendChild(emptyRow);
        } else {
            // Agregar filas para cada producto
            carrito.forEach((producto, index) => {
                const subtotal = producto.precio * producto.cantidad;
                total += subtotal;
                
                const row = document.createElement("tr");
                row.className = "fade-in";
                row.style.animationDelay = `${index * 0.05}s`;
                row.innerHTML = `
                    <td class="small text-truncate" style="max-width: 120px;" title="${producto.nombre}">${producto.nombre}</td>
                    <td class="text-center">
                        <input type="number" class="form-control form-control-sm cantidad-input" 
                               data-id="${producto.id}" value="${producto.cantidad}" min="1" max="${producto.stock}">
                    </td>
                    <td class="text-center small">C$ ${producto.precio.toFixed(2)}</td>
                    <td class="text-center">
                        <button class="btn btn-danger btn-sm eliminar" data-id="${producto.id}">
                            <i class="fas fa-trash-alt"></i>
                        </button>
                    </td>
                `;
                carritoTable.appendChild(row);
            });
        }
        
        // Actualizar total
        const descuento = parseFloat(document.getElementById("descuento").value) || 0;
        const totalFinal = total - descuento;
        totalSpan.textContent = `C$ ${totalFinal.toFixed(2)}`;
        
        // Ajustar scroll del carrito
        ajustarScrollCarrito();
        
        // Habilitar/deshabilitar botones según estado del carrito
        btnPagar.disabled = carrito.length === 0;
        btnVaciarCarrito.disabled = carrito.length === 0;
    }

    // Ajustar scroll del carrito
    function ajustarScrollCarrito() {
        if (carrito.length > 3) {
            carritoTablaContainer.classList.add("has-scroll");
        } else {
            carritoTablaContainer.classList.remove("has-scroll");
        }
    }

    // Cambiar cantidad de productos
    carritoTable.addEventListener("change", function (e) {
        if (e.target.classList.contains("cantidad-input")) {
            const id = e.target.dataset.id;
            let nuevaCantidad = parseInt(e.target.value);
            const producto = carrito.find(p => p.id === id);

            if (producto) {
                if (isNaN(nuevaCantidad) || nuevaCantidad < 1) {
                    nuevaCantidad = 1;
                    e.target.value = 1;
                } else if (nuevaCantidad > producto.stock) {
                    nuevaCantidad = producto.stock;
                    e.target.value = producto.stock;
                    mostrarNotificacion(`Solo hay ${producto.stock} unidades disponibles de "${producto.nombre}"`, "warning");
                }

                producto.cantidad = nuevaCantidad;
                actualizarCarrito();
            }
        }
    });


    // Eliminar producto del carrito
    carritoTable.addEventListener("click", function (e) {
        const botonEliminar = e.target.closest(".eliminar");
        if (botonEliminar) {
            const id = botonEliminar.dataset.id;
            const producto = carrito.find(p => p.id === id);
            
            if (producto) {
                // Efecto visual antes de eliminar
                const row = botonEliminar.closest("tr");
                row.style.transition = "all 0.3s ease";
                row.style.opacity = "0";
                row.style.transform = "translateX(20px)";
                
                setTimeout(() => {
                    carrito = carrito.filter(p => p.id !== id);
                    actualizarCarrito();
                    mostrarNotificacion(`"${producto.nombre}" eliminado del carrito`, "warning");
                }, 300);
            }
        }
    });

    // Aplicar descuento
    document.getElementById("descuento").addEventListener("input", function() {
        const descuento = parseFloat(this.value) || 0;
        if (descuento < 0) {
            this.value = 0;
            return;
        }
        
        const total = carrito.reduce((acc, p) => acc + p.precio * p.cantidad, 0);
        
        if (descuento > total) {
            this.value = total.toFixed(2);
            mostrarNotificacion("El descuento no puede ser mayor al total", "warning");
        }
        
        actualizarCarrito();
    });

    // FILTRO POR NOMBRE Y CATEGORÍA con debounce
    let timeoutId;
    function filtrarProductos() {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => {
            const textoBusqueda = buscarInput.value.toLowerCase();
            const categoriaSeleccionada = filtroCategoria.value;
            let productosVisibles = 0;

            document.querySelectorAll(".producto-card").forEach(function (card) {
                const nombre = card.getAttribute("data-nombre") || card.querySelector(".card-title").textContent.toLowerCase();
                const categoria = card.getAttribute("data-categoria");

                // Muestra solo si coincide con la búsqueda y la categoría seleccionada
                const coincideBusqueda = nombre.includes(textoBusqueda);
                const coincideCategoria = categoriaSeleccionada === "0" || categoria === categoriaSeleccionada;

                if (coincideBusqueda && coincideCategoria) {
                    card.style.display = "";
                    productosVisibles++;
                    
                    // Animación de aparición
                    card.classList.add("fade-in");
                    setTimeout(() => {
                        card.classList.remove("fade-in");
                    }, 500);
                } else {
                    card.style.display = "none";
                }
            });

            // Mostrar mensaje si no hay resultados
            if (productosVisibles === 0) {
                noResultadosDiv.classList.remove("d-none");
            } else {
                noResultadosDiv.classList.add("d-none");
            }
        }, 300);
    }

    // Eventos de búsqueda y filtrado
    buscarInput.addEventListener("input", filtrarProductos);
    filtroCategoria.addEventListener("change", filtrarProductos);


    function buscarClientes() {
        const termino = document.getElementById('buscarCliente').value.trim();
        if (termino.length < 2) {
            alert('Ingrese al menos 2 caracteres para buscar');
            return;
        }

        fetch('/buscar-clientes', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ termino: termino })
        })
        .then(async response => {
            if (!response.ok) {
                let errorMsg = 'Error al buscar clientes';
                try {
                    const data = await response.json();
                    errorMsg = data.error || errorMsg;
                } catch {
                    errorMsg = await response.text();
                }
                throw new Error(errorMsg);
            }
            return response.json();
        })
        .then(data => {
            const $lista = $('#listaClientes');
            $lista.empty();
            

            if (data.clientes && data.clientes.length > 0) {
                data.clientes.forEach(cliente => {
                    $lista.append(`<option value="${cliente.IDCliente}" 
                                    data-nombre="${cliente.NombreCompleto}" 
                                    data-telefono="${cliente.Telefono}">
                        ${cliente.NombreCompleto} - ${cliente.Telefono}
                    </option>`);
                });
                $('#resultadosCliente').show();
                listaClientes.size = 1;
            } else {
                $lista.append('<option disabled selected>No se encontraron clientes</option>');
                $('#resultadosCliente').show();
            }
        })
        .catch(error => {
            alert(error.message);
        });
    }

    // Toggle entre cliente existente y nuevo
    $('#clienteExistenteCheck').change(function() {
        if ($(this).is(':checked')) {
            $('#clienteExistenteSection').show();
            $('#nuevoClienteSection').hide();
            $('#clienteNombre, #clienteTelefono').val('');
        } else {
            $('#clienteExistenteSection').hide();
            $('#nuevoClienteSection').show();
            $('#buscarCliente').val('');
            $('#resultadosCliente').hide();
        }
    });

    // Buscar cliente
    $('#btnBuscarCliente').click(buscarClientes);
    $('#buscarCliente').keyup(function(e) {
        if (e.keyCode === 13) {
            buscarClientes();
        }
    });

    
    // Mostrar modal de pago
    btnPagar.addEventListener("click", function () {
        if (carrito.length === 0) {
            mostrarNotificacion("El carrito está vacío", "warning");
            return;
        }

        const total = calcularTotalFinal();
        totalPagoInput.value = `C$ ${total.toFixed(2)}`;
        
        // Limpiar campos
        dineroRecibidoInput.value = "";
        cambioInput.value = "0.00";
        dineroRecibidoInput.classList.remove("is-invalid");
        dineroRecibidoFeedback.textContent = "";
        
        // Mostrar modal
        modalPago.show();
    });

    // Calcular cambio
    dineroRecibidoInput.addEventListener("input", function () {
        const total = parseFloat(totalPagoInput.value.replace("C$ ", ""));
        const recibido = parseFloat(dineroRecibidoInput.value) || 0;
        const cambio = recibido - total;
        
        cambioInput.value = cambio >= 0 ? cambio.toFixed(2) : '0.00';
        
        // Validar solo si es pago en efectivo
        if (tipoPagoSelect.value === "efectivo") {
            if (recibido < total) {
                dineroRecibidoInput.classList.add("is-invalid");
                dineroRecibidoFeedback.textContent = "La cantidad recibida es menor al total";
            } else {
                dineroRecibidoInput.classList.remove("is-invalid");
                dineroRecibidoFeedback.textContent = "";
            }
        } else {
            dineroRecibidoInput.classList.remove("is-invalid");
            dineroRecibidoFeedback.textContent = "";
        }
    });
    
    // Cambiar validación según método de pago
    tipoPagoSelect.addEventListener("change", function() {
        if (this.value !== "efectivo") {
            dineroRecibidoInput.classList.remove("is-invalid");
            dineroRecibidoFeedback.textContent = "";
            
            if (this.value === "tarjeta" || this.value === "transferencia") {
                dineroRecibidoInput.value = totalPagoInput.value.replace("C$ ", "");
                cambioInput.value = "0.00";
            }
        } else {
            // Validar nuevamente si es efectivo
            const total = parseFloat(totalPagoInput.value.replace("C$ ", ""));
            const recibido = parseFloat(dineroRecibidoInput.value) || 0;
            
            if (recibido < total) {
                dineroRecibidoInput.classList.add("is-invalid");
                dineroRecibidoFeedback.textContent = "La cantidad recibida es menor al total";
            }
        }
    });
    // variable para almacenar el cliente seleccionado
    let clienteSeleccionadoId = null;
    let clienteSeleccionadoNombre = '';
    let clienteSeleccionadoTelefono = '';

    const listaClientes = document.getElementById('listaClientes');

// Expande el select al hacer click
listaClientes.addEventListener('mousedown', function(e) {
    if (this.options.length > 1) {
        this.size = this.options.length;
    }
});

    // Contrae el select al perder el foco
    listaClientes.addEventListener('blur', function(e) {
        this.size = 1;
    });

    // Contrae el select y deja solo la opción seleccionada visible al elegir
    listaClientes.addEventListener('change', function(e) {
        this.size = 1;
        // Opcional: si quieres ocultar las demás opciones después de seleccionar
        for (let i = 0; i < this.options.length; i++) {
            this.options[i].style.display = (i === this.selectedIndex) ? '' : 'none';
        }
        // Si quieres permitir volver a expandir, puedes restaurar las opciones al hacer click en "Cambiar cliente"
    });

    $('#listaClientes').on('change', function() {
        const selectedIndex = this.selectedIndex;
        const options = this.options;

        // Oculta todas las opciones excepto la seleccionada
        for (let i = 0; i < options.length; i++) {
            if (i !== selectedIndex) {
                options[i].style.display = 'none';
            } else {
                options[i].style.display = '';
            }
        }

        // Ajusta el tamaño del select a una fila
        this.size = 1;

        // Opcional: muestra un botón para cambiar de cliente
        if (!document.getElementById('btnCambiarCliente')) {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'btn btn-link btn-sm mt-2';
            btn.id = 'btnCambiarCliente';
            btn.textContent = 'Cambiar cliente';
            btn.onclick = () => {
                // Muestra todas las opciones de nuevo
                for (let i = 0; i < options.length; i++) {
                    options[i].style.display = '';
                }
                $('#listaClientes').val(''); // Deselecciona
                this.size = options.length; // Restaura el tamaño original
                btn.remove();
            };
            this.parentNode.appendChild(btn);
        }
    });

    // Finalizar pago
    finalizarPagoBtn.addEventListener("click", function () {
        if (!validarFormularioPago()) return;

        // Recopilar datos
        const clienteNombre = document.getElementById('clienteNombre').value;
        const clienteTelefono = document.getElementById('clienteTelefono').value;
        const tipoPago = tipoPagoSelect.value;
        const dineroRecibido = parseFloat(dineroRecibidoInput.value) || 0;
        const cambio = parseFloat(cambioInput.value) || 0;
        const notaVenta = document.getElementById('notaVenta').value;
        const descuento = parseFloat(document.getElementById("descuento").value) || 0;
        const total = calcularTotalFinal();

        // Detectar si es cliente existente
        const esClienteExistente = $('#clienteExistenteCheck').is(':checked');
        let datosCliente = {};

        if (esClienteExistente && clienteSeleccionadoId) {
            datosCliente = {
                cliente_id: clienteSeleccionadoId
            };
        } else if (!esClienteExistente && (clienteNombre || clienteTelefono)) {
            datosCliente = {
                cliente_nombre: clienteNombre || null,
                cliente_telefono: clienteTelefono || null
            };
        } // Si no hay datos, se enviará venta general (sin cliente)

        // Enviar datos al servidor
        fetch('/guardar_venta', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                carrito,
                total,
                descuento,
                tipo_pago: tipoPago,
                dinero_recibido: dineroRecibido,
                cambio,
                nota: notaVenta || '',
                ...datosCliente // Aquí se agregan los datos del cliente según el caso
            })
        })
        .then(response => response.json())
        .then(data => {
                    finalizarPagoBtn.disabled = false;
                    finalizarPagoBtn.innerHTML = '<i class="fas fa-check-circle me-2"></i>Finalizar Venta';
                    if (data.success) {
                                ventaActual = {
                    numeroFactura: generarNumeroFactura(),
                    subtotal: carrito.reduce((acc, p) => acc + p.precio * p.cantidad, 0),
                    descuento: descuento,
                    total: total,
                    productos: carrito.map(p => ({
                        nombre: p.nombre,
                        cantidad: p.cantidad,
                        precio: p.precio
                    })),
                    cliente: {
                        nombre: clienteSeleccionadoNombre || clienteNombre || 'Cliente General',
                        telefono: clienteSeleccionadoTelefono || clienteTelefono || ''
                    },
                    fecha: new Date().toLocaleDateString(),
                    hora: new Date().toLocaleTimeString(),
                    tipoPago: tipoPago,
                    nota: notaVenta
                };
                modalPago.hide();
                mostrarModalFactura(ventaActual);
                if (data.ventaId) ventaActual.id = data.ventaId;
            } else {
                Swal.fire({
                    icon: 'error',
                    title: 'Error',
                    text: data.error || 'Ocurrió un error al procesar la venta',
                    confirmButtonColor: '#e74a3b'
                });
            }
        })
        .catch(error => {
            finalizarPagoBtn.disabled = false;
            finalizarPagoBtn.innerHTML = '<i class="fas fa-check-circle me-2"></i>Finalizar Venta';
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: error.message || 'Ocurrió un error al procesar la venta. Intente nuevamente.',
                confirmButtonColor: '#e74a3b'
            });
        });
    });

    // Mostrar modal con previsualización de factura
    function mostrarModalFactura(venta) {
        // Crear HTML de la factura
        const facturaHTML = generarHTMLFactura(venta);
        
        Swal.fire({
            title: 'Venta Completada',
            html: `
                <div class="success-modal-content">
                    <div class="text-center mb-3">
                        <i class="fas fa-check-circle text-success fa-3x mb-3"></i>
                        <h5>Venta registrada con éxito</h5>
                    </div>
                    
                    <div class="invoice-preview" id="facturaPreview">
                        ${facturaHTML}
                    </div>
                    
                    <div class="invoice-actions">
                        <button class="btn btn-primary btn-invoice" id="btnDescargarPDF">
                            <i class="fas fa-file-pdf"></i>Descargar PDF
                        </button>
                        <button class="btn btn-success btn-invoice" id="btnImprimirFactura">
                            <i class="fas fa-print"></i>Imprimir Factura
                        </button>
                    </div>
                </div>
            `,
            showConfirmButton: true,
            confirmButtonText: 'Cerrar',
            confirmButtonColor: '#4e73df',
            width: '800px',
            didOpen: () => {
                // Configurar eventos para los botones
                document.getElementById('btnDescargarPDF').addEventListener('click', () => {
                    generarPDF(venta);
                });
                
                document.getElementById('btnImprimirFactura').addEventListener('click', () => {
                    imprimirFactura();
                });
            }
        }).then(() => {
            location.reload();
        });
    }

    // Generar HTML de la factura
    function generarHTMLFactura(venta) {
        // Calcular totales
        const subtotalFormateado = venta.subtotal.toFixed(2);
        const descuentoFormateado = venta.descuento.toFixed(2);
        const totalFormateado = venta.total.toFixed(2);
        
        // Generar filas de productos
        const filasProductos = venta.productos.map(producto => {
            const subtotal = (producto.precio * producto.cantidad).toFixed(2);
            return `
                <tr>
                    <td>${producto.nombre}</td>
                    <td class="text-center">${producto.cantidad}</td>
                    <td class="text-end">C$ ${producto.precio.toFixed(2)}</td>
                    <td class="text-end">C$ ${subtotal}</td>
                </tr>
            `;
        }).join('');
        
        // Generar HTML completo de la factura
        return `
            <div class="invoice-header">
                <div class="invoice-title">FACTURA</div>
                <div class="invoice-subtitle">Nº ${venta.numeroFactura}</div>
            </div>
            
            <div class="invoice-info">
                <div class="invoice-info-section">
                    <div class="invoice-info-title">DATOS DEL CLIENTE</div>
                    <div class="invoice-info-item"><strong>Cliente:</strong> ${venta.cliente.nombre}</div>
                    <div class="invoice-info-item"><strong>Telefono:</strong> ${venta.cliente.telefono}</div>
                </div>
                
                <div class="invoice-info-section text-end">
                    <div class="invoice-info-title">INFORMACIÓN DE VENTA</div>
                    <div class="invoice-info-item"><strong>Fecha:</strong> ${venta.fecha}</div>
                    <div class="invoice-info-item"><strong>Hora:</strong> ${venta.hora}</div>
                    <div class="invoice-info-item"><strong>Método de pago:</strong> ${venta.tipoPago.charAt(0).toUpperCase() + venta.tipoPago.slice(1)}</div>
                </div>
            </div>
            
            <table class="invoice-table">
                <thead>
                    <tr>
                        <th>Producto</th>
                        <th class="text-center">Cantidad</th>
                        <th class="text-end">Precio</th>
                        <th class="text-end">Subtotal</th>
                    </tr>
                </thead>
                <tbody>
                    ${filasProductos}
                </tbody>
            </table>
            
            <div class="invoice-total">
                <div class="invoice-total-row">
                    <span class="invoice-total-label">Subtotal:</span>
                    <span class="invoice-total-value">C$ ${subtotalFormateado}</span>
                </div>
                <div class="invoice-total-row">
                    <span class="invoice-total-label">Descuento:</span>
                    <span class="invoice-total-value">C$ ${descuentoFormateado}</span>
                </div>
                <div class="invoice-total-final">
                    <span>TOTAL:</span>
                    <span>C$ ${totalFormateado}</span>
                </div>
            </div>
            
            ${venta.nota ? `
                <div class="mt-3 pt-2 border-top">
                    <div class="invoice-info-title">NOTAS</div>
                    <div class="invoice-info-item">${venta.nota}</div>
                </div>
            ` : ''}
            
            <div class="invoice-footer">
                <p>Gracias por su compra</p>
            </div>
            
            <div class="watermark">FACTURA</div>
        `;
    }

    // Generar PDF de la factura
    function generarPDF(venta) {
        // Importar jsPDF desde el objeto window
        const { jsPDF } = window.jspdf;
        
        // Crear nuevo documento PDF
        const doc = new jsPDF({
            orientation: 'portrait',
            unit: 'mm',
            format: 'a4'
        });
        
        // Configurar fuentes y estilos
        doc.setFont('helvetica', 'normal');
        doc.setFontSize(10);
        
        // Añadir encabezado
        doc.setFontSize(18);
        doc.setFont('helvetica', 'bold');
        doc.text('FACTURA', 105, 20, { align: 'center' });
        
        doc.setFontSize(12);
        doc.text(`Nº ${venta.numeroFactura}`, 105, 27, { align: 'center' });
        
        // Añadir marca de agua
        doc.setFontSize(60);
        doc.setTextColor(240, 240, 240);
        doc.text('FACTURA', 105, 140, { align: 'center', angle: 45 });
        doc.setTextColor(0, 0, 0);
        
        // Información de la empresa (puedes personalizar esto)
        doc.setFontSize(10);
        doc.setFont('helvetica', 'normal');
        doc.text('Librería Indiana', 20, 40);
        doc.text('Dirección: Vanegas, Esquipulas.', 20, 45);
        doc.text('Del colegio Pablo Antonio Cuadras 500 mts al oeste', 20, 50);
        doc.text('Teléfono: (505) 7756-5332', 20, 55);
        doc.text('Email: info@libreriaindiana.com', 20, 60);

        // Información de la factura
        doc.setFont('helvetica', 'bold');
        doc.text('INFORMACIÓN DE VENTA:', 140, 40);
        doc.setFont('helvetica', 'normal');
        doc.text(`Fecha: ${venta.fecha}`, 140, 45);
        doc.text(`Hora: ${venta.hora}`, 140, 50);
        doc.text(`Método de pago: ${venta.tipoPago.charAt(0).toUpperCase() + venta.tipoPago.slice(1)}`, 140, 55);
        
        // Información del cliente
        doc.setFont('helvetica', 'bold');
        doc.text('CLIENTE:', 20, 65);
        doc.setFont('helvetica', 'normal');
        doc.text(`Nombre: ${venta.cliente.nombre}`, 20, 70);
        doc.text(`Telefono: ${venta.cliente.telefono}`, 20, 75);
        
        // Línea separadora
        doc.setDrawColor(100, 100, 100);
        doc.line(20, 80, 190, 80);
        
        // Tabla de productos
        const headers = [['Producto', 'Cantidad', 'Precio', 'Subtotal']];
        
        const data = venta.productos.map(producto => [
            producto.nombre,
            producto.cantidad.toString(),
            `C$ ${producto.precio.toFixed(2)}`,
            `C$ ${(producto.precio * producto.cantidad).toFixed(2)}`
        ]);
        
        doc.autoTable({
            head: headers,
            body: data,
            startY: 85,
            theme: 'grid',
            headStyles: {
                fillColor: [78, 115, 223],
                textColor: 255,
                fontStyle: 'bold'
            },
            columnStyles: {
                0: { cellWidth: 80 },
                1: { cellWidth: 25, halign: 'center' },
                2: { cellWidth: 35, halign: 'right' },
                3: { cellWidth: 35, halign: 'right' }
            },
            styles: {
                fontSize: 9,
                cellPadding: 3
            }
        });
        
        // Calcular posición Y después de la tabla
        const finalY = doc.lastAutoTable.finalY + 10;
        
        // Totales
        doc.setFont('helvetica', 'normal');
        doc.text(`Subtotal:`, 150, finalY);
        doc.text(`C$ ${venta.subtotal.toFixed(2)}`, 190, finalY, { align: 'right' });
        
        doc.text(`Descuento:`, 150, finalY + 5);
        doc.text(`C$ ${venta.descuento.toFixed(2)}`, 190, finalY + 5, { align: 'right' });
        
        // Línea para el total
        doc.setDrawColor(78, 115, 223);
        doc.line(150, finalY + 7, 190, finalY + 7);
        
        doc.setFont('helvetica', 'bold');
        doc.text(`TOTAL:`, 150, finalY + 12);
        doc.text(`C$ ${venta.total.toFixed(2)}`, 190, finalY + 12, { align: 'right' });
        
        // Notas
        if (venta.nota) {
            doc.setFont('helvetica', 'bold');
            doc.text('NOTAS:', 20, finalY + 20);
            doc.setFont('helvetica', 'normal');
            
            // Dividir notas largas en múltiples líneas
            const splitNota = doc.splitTextToSize(venta.nota, 170);
            doc.text(splitNota, 20, finalY + 25);
        }
        
        // Pie de página
        const pageHeight = doc.internal.pageSize.height;
        doc.setFont('helvetica', 'italic');
        doc.setFontSize(8);
        doc.text('Gracias por su compra', 105, pageHeight - 20, { align: 'center' });
        
        // Guardar PDF
        doc.save(`Factura_${venta.numeroFactura}.pdf`);
    }

    // Imprimir factura
    function imprimirFactura() {
        const facturaPreview = document.getElementById('facturaPreview');
        const ventanaImpresion = window.open('', '_blank');
        
        ventanaImpresion.document.write(`
            <html>
                <head>
                    <title>Factura ${ventaActual.numeroFactura}</title>
                    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
                    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css" rel="stylesheet">
                    <style>
                        body {
                            font-family: Arial, sans-serif;
                            padding: 20px;
                            max-width: 800px;
                            margin: 0 auto;
                        }
                        
                        .invoice-header {
                            border-bottom: 2px solid #4e73df;
                            padding-bottom: 1rem;
                            margin-bottom: 1.5rem;
                        }
                        
                        .invoice-title {
                            font-size: 1.5rem;
                            font-weight: 700;
                            color: #4e73df;
                            margin-bottom: 0.5rem;
                        }
                        
                        .invoice-subtitle {
                            font-size: 0.9rem;
                            color: #6c757d;
                        }
                        
                        .invoice-info {
                            display: flex;
                            justify-content: space-between;
                            margin-bottom: 1.5rem;
                        }
                        
                        .invoice-info-section {
                            flex: 1;
                        }
                        
                        .invoice-info-title {
                            font-weight: 600;
                            font-size: 0.9rem;
                            color: #5a5c69;
                            margin-bottom: 0.5rem;
                        }
                        
                        .invoice-info-item {
                            font-size: 0.85rem;
                            margin-bottom: 0.25rem;
                        }
                        
                        .invoice-table {
                            width: 100%;
                            margin-bottom: 1.5rem;
                            font-size: 0.85rem;
                            border-collapse: collapse;
                        }
                        
                        .invoice-table th {
                            background-color: #f8f9fc;
                            font-weight: 600;
                            text-transform: uppercase;
                            font-size: 0.75rem;
                            padding: 0.75rem;
                            border-bottom: 1px solid #e3e6f0;
                        }
                        
                        .invoice-table td {
                            padding: 0.75rem;
                            border-bottom: 1px solid #e3e6f0;
                        }
                        
                        .invoice-total {
                            display: flex;
                            flex-direction: column;
                            align-items: flex-end;
                            margin-top: 1rem;
                        }
                        
                        .invoice-total-row {
                            display: flex;
                            justify-content: space-between;
                            width: 200px;
                            margin-bottom: 0.25rem;
                        }
                        
                        .invoice-total-label {
                            font-weight: 600;
                            color: #5a5c69;
                        }
                        
                        .invoice-total-value {
                            font-weight: 700;
                        }
                        
                        .invoice-total-final {
                            font-size: 1.1rem;
                            font-weight: 700;
                            color: #4e73df;
                            border-top: 2px solid #4e73df;
                            padding-top: 0.5rem;
                            margin-top: 0.5rem;
                            width: 200px;
                            display: flex;
                            justify-content: space-between;
                        }
                        
                        .invoice-footer {
                            margin-top: 2rem;
                            padding-top: 1rem;
                            border-top: 1px solid #e3e6f0;
                            font-size: 0.8rem;
                            color: #6c757d;
                            text-align: center;
                        }
                        
                        .text-end {
                            text-align: right;
                        }
                        
                        .text-center {
                            text-align: center;
                        }
                        
                        @media print {
                            body {
                                padding: 0;
                                margin: 0;
                            }
                            
                            .watermark {
                                display: none;
                            }
                        }
                    </style>
                </head>
                <body>
                    ${facturaPreview.innerHTML}
                    <script>
                        window.onload = function() {
                            window.print();
                            window.setTimeout(function() {
                                window.close();
                            }, 500);
                        }
                    </script>
                </body>
            </html>
        `);
        
        ventanaImpresion.document.close();
    }

    // Generar número de factura único
    function generarNumeroFactura() {
        const fecha = new Date();
        const año = fecha.getFullYear().toString().substr(-2);
        const mes = (fecha.getMonth() + 1).toString().padStart(2, '0');
        const dia = fecha.getDate().toString().padStart(2, '0');
        const aleatorio = Math.floor(Math.random() * 10000).toString().padStart(4, '0');
        
        return `F${año}${mes}${dia}-${aleatorio}`;
    }

    // Validar formulario de pago
    function validarFormularioPago() {
        let esValido = true;
        
        // Validar cantidad recibida para pagos en efectivo
        if (tipoPagoSelect.value === "efectivo") {
            const total = parseFloat(totalPagoInput.value.replace("C$ ", ""));
            const recibido = parseFloat(dineroRecibidoInput.value) || 0;
            
            if (recibido < total) {
                dineroRecibidoInput.classList.add("is-invalid");
                dineroRecibidoFeedback.textContent = "La cantidad recibida es menor al total";
                dineroRecibidoInput.focus();
                esValido = false;
            } else {
                dineroRecibidoInput.classList.remove("is-invalid");
                dineroRecibidoFeedback.textContent = "";
            }
        }
        
        // Validar que haya productos en el carrito
        if (carrito.length === 0) {
            mostrarNotificacion("El carrito está vacío", "error");
            esValido = false;
        }
        
        return esValido;
    }

    // Vaciar carrito
    btnVaciarCarrito.addEventListener("click", function () {
        if (carrito.length === 0) {
            mostrarNotificacion("El carrito ya está vacío", "info");
            return;
        }

        Swal.fire({
            title: '¿Vaciar carrito?',
            text: "Se eliminarán todos los productos del carrito",
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#e74a3b',
            cancelButtonColor: '#6c757d',
            confirmButtonText: 'Sí, vaciar',
            cancelButtonText: 'Cancelar'
        }).then((result) => {
            if (result.isConfirmed) {
                limpiarCarrito();
                mostrarNotificacion("Carrito vaciado correctamente", "success");
            }
        });
    });

    // Limpiar carrito
    function limpiarCarrito() {
        carrito = [];
        document.getElementById('descuento').value = '';
        actualizarCarrito();
    }
    
    // Calcular total final (con descuento)
    function calcularTotalFinal() {
        const subtotal = carrito.reduce((acc, p) => acc + p.precio * p.cantidad, 0);
        const descuento = parseFloat(document.getElementById("descuento").value) || 0;
        return subtotal - descuento;
    }

    // Mostrar notificación
    function mostrarNotificacion(mensaje, tipo = "info") {
        // Limpiar notificación anterior si existe
        if (notificacionTimeout) {
            clearTimeout(notificacionTimeout);
            const notificacionAnterior = document.querySelector('.notification');
            if (notificacionAnterior) {
                notificacionAnterior.remove();
            }
        }
        
        // Crear nueva notificación
        const notificacion = document.createElement('div');
        notificacion.className = `notification ${tipo}`;
        
        // Icono según tipo
        let icono = 'info-circle';
        if (tipo === 'success') icono = 'check-circle';
        if (tipo === 'warning') icono = 'exclamation-triangle';
        if (tipo === 'error') icono = 'times-circle';
        
        notificacion.innerHTML = `
            <i class="fas fa-${icono}"></i>
            <span>${mensaje}</span>
        `;
        
        // Añadir al DOM
        document.body.appendChild(notificacion);
        
        // Eliminar después de 3 segundos
        notificacionTimeout = setTimeout(() => {
            notificacion.style.opacity = '0';
            notificacion.style.transform = 'translateX(20px)';
            setTimeout(() => notificacion.remove(), 300);
        }, 3000);
    }
});