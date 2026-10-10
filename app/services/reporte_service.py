import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta, date
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

from app.repositories.reporte_repository import ReporteRepository

class ReporteService:
    """Maneja la lógica de negocio para la generación de Dashboards y Reportes financieros"""

    @staticmethod
    def _build_where_clause(filters):
        """Helper para construir fragmentos de consulta WHERE"""
        where_conditions = []
        params = []
        
        if filters.get('fecha_inicio'):
            where_conditions.append('DATE(fecha) >= ?')
            params.append(filters['fecha_inicio'])
        
        if filters.get('fecha_fin'):
            where_conditions.append('DATE(fecha) <= ?')
            params.append(filters['fecha_fin'])
            
        where_clause = 'WHERE ' + ' AND '.join(where_conditions) if where_conditions else ''
        return where_clause, params

    @staticmethod
    def get_kpis(filters):
        """Calcula los KPIs del negocio: ventas, compras, márgenes y crecimientos."""
        where_clause, params = ReporteService._build_where_clause(filters)
        
        total_sales = ReporteRepository.obtener_sumatoria_balance('Venta', where_clause, params)
        total_purchases = ReporteRepository.obtener_sumatoria_balance('Compra', where_clause, params)
        
        net_profit = total_sales - total_purchases
        profit_margin = (net_profit / total_sales * 100) if total_sales > 0 else 0
        
        # Calcular crecimiento vs período anterior
        sales_growth = ReporteService.calculate_growth('Venta', 'Total', filters)
        purchases_growth = ReporteService.calculate_growth('Compra', 'Total', filters)
        profit_growth = sales_growth - purchases_growth
        margin_growth = profit_margin  # Placeholder simple para el delta temporal si se calculara
        
        return {
            'total_sales': float(total_sales),
            'total_purchases': float(total_purchases),
            'net_profit': float(net_profit),
            'profit_margin': float(profit_margin),
            'sales_growth': float(sales_growth),
            'purchases_growth': float(purchases_growth),
            'profit_growth': float(profit_growth),
            'margin_growth': float(margin_growth)
        }

    @staticmethod
    def calculate_growth(table, column, filters):
        """Calcula crecimiento vs período anterior asumiendo la misma ventana de tiempo"""
        fecha_inicio = filters.get('fecha_inicio')
        fecha_fin = filters.get('fecha_fin')
        
        if not fecha_inicio or not fecha_fin:
            return 0
        
        start_date = datetime.strptime(fecha_inicio, '%Y-%m-%d')
        end_date = datetime.strptime(fecha_fin, '%Y-%m-%d')
        duration = (end_date - start_date).days
        
        prev_end = start_date - timedelta(days=1)
        prev_start = prev_end - timedelta(days=duration)
        
        current_where, current_params = ReporteService._build_where_clause(filters)
        current_total = ReporteRepository.obtener_sumatoria_balance(table, current_where, current_params)
        
        prev_filters = {
            'fecha_inicio': prev_start.strftime('%Y-%m-%d'),
            'fecha_fin': prev_end.strftime('%Y-%m-%d')
        }
        prev_where, prev_params = ReporteService._build_where_clause(prev_filters)
        prev_total = ReporteRepository.obtener_sumatoria_balance(table, prev_where, prev_params)
        
        if prev_total > 0:
            growth = ((current_total - prev_total) / prev_total) * 100
        else:
            growth = 100 if current_total > 0 else 0
            
        return growth

    @staticmethod
    def get_transactions(filters):
        """Obtener todas las transacciones de ingresos y gastos combinadas e intercaladas."""
        where_clause, params = ReporteService._build_where_clause(filters)
        
        ventas = ReporteRepository.obtener_transacciones_ventas_balance(where_clause, params)
        compras = ReporteRepository.obtener_transacciones_compras_balance(where_clause, params)
        
        transactions = []
        transactions.extend(ventas)
        transactions.extend(compras)
        
        # Ordenar por fecha cronológicamente para calcular balances vivos
        transactions.sort(key=lambda x: x['date'], reverse=False)
        
        running_balance = 0
        for transaction in transactions:
            running_balance += transaction['balance']  # compras_balance es negativo desde el repo
            transaction['balance'] = running_balance
            
        # Retornar invertido para que la vista lo muestre más reciente primero
        transactions.reverse()
        return transactions

    @staticmethod
    def get_income_expense_chart_data(filters, period):
        """Datos transformados para Charts JS"""
        if period == 'monthly':
            date_trunc = "strftime('%Y-%m', fecha)"
        elif period == 'quarterly':
            date_trunc = "strftime('%Y', fecha) || '-Q' || ((CAST(strftime('%m', fecha) AS INTEGER) - 1) / 3 + 1)"
        else:  # yearly
            date_trunc = "strftime('%Y', fecha)"
            
        where_clause, params = ReporteService._build_where_clause(filters)
        
        ingresos = ReporteRepository.obtener_agrupados_por_periodo('Venta', date_trunc, where_clause, params)
        egresos = ReporteRepository.obtener_agrupados_por_periodo('Compra', date_trunc, where_clause, params)
        
        periods = set()
        income_dict = {}
        expense_dict = {}
        
        for row in ingresos:
            periods.add(row['period'])
            income_dict[row['period']] = float(row['total'])
            
        for row in egresos:
            periods.add(row['period'])
            expense_dict[row['period']] = float(row['total'])
            
        sorted_periods = sorted(list(periods))
        
        return {
            'labels': sorted_periods,
            'income': [income_dict.get(p, 0) for p in sorted_periods],
            'expenses': [expense_dict.get(p, 0) for p in sorted_periods]
        }

    @staticmethod
    def get_grouped_transactions(filters, group_by='daily'):
        """Obtener transacciones agrupadas por período"""
        if group_by == 'weekly':
            date_format = "strftime('%Y-W%W', fecha)"
        elif group_by == 'monthly':
            date_format = "strftime('%Y-%m', fecha)"
        else:  # daily
            date_format = "DATE(fecha)"
            
        where_clause, params = ReporteService._build_where_clause(filters)
        
        ingresos = ReporteRepository.obtener_agrupados_por_periodo('Venta', date_format, where_clause, params)
        egresos = ReporteRepository.obtener_agrupados_por_periodo('Compra', date_format, where_clause, params)
        
        periods = set()
        income_dict = {}
        expense_dict = {}
        
        for row in ingresos:
            periods.add(row['period'])
            income_dict[row['period']] = float(row['total'])
            
        for row in egresos:
            periods.add(row['period'])
            expense_dict[row['period']] = float(row['total'])
            
        transactions = []
        for period in sorted(periods):
            income = income_dict.get(period, 0)
            expense = expense_dict.get(period, 0)
            balance = income - expense
            transactions.append({
                'period': period,
                'income': income,
                'expense': expense,
                'balance': balance
            })
            
        return transactions

    @staticmethod
    def generate_pdf_report(filters):
        """Generar archivo PDF en un BytesIO buffer"""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20, bottomMargin=20)
        styles = getSampleStyleSheet()
        story = []
        
        title_style = ParagraphStyle(
            'CustomTitle', parent=styles['Heading1'], fontSize=20, spaceAfter=20,
            alignment=1, textColor=colors.HexColor('#4361ee')
        )
        subtitle_style = ParagraphStyle(
            'CustomSubtitle', parent=styles['Heading2'], fontSize=14, spaceAfter=15,
            textColor=colors.HexColor('#4361ee')
        )
        
        story.append(Paragraph("LIBRERÍA INDIANA", title_style))
        story.append(Spacer(1, 10))
        company_info = "<b>Dirección:</b> Vanegas, Esquipulas<br/>Del colegio Pablo Antonio Cuadras 500 mts al oeste<br/><b>Teléfono:</b> (505) 7756-5332<br/><b>Email:</b> indianaflores2@gmail.com"
        story.append(Paragraph(company_info, styles['Normal']))
        story.append(Spacer(1, 20))
        
        story.append(Paragraph("BALANCE GENERAL DEL NEGOCIO", title_style))
        story.append(Spacer(1, 10))
        
        filter_info = "<b>Filtros Aplicados:</b><br/>"
        if filters.get('fecha_inicio') and filters.get('fecha_fin'):
            filter_info += f"Período: {filters['fecha_inicio']} al {filters['fecha_fin']}<br/>"
        else:
            filter_info += "Ningún filtro de fecha aplicado - Mostrando todos los datos"
        story.append(Paragraph(filter_info, styles['Normal']))
        story.append(Spacer(1, 20))
        
        kpis = ReporteService.get_kpis(filters)
        grouped_transactions = ReporteService.get_grouped_transactions(filters, 'daily')
        top_products = ReporteRepository.obtener_top_productos(filters, limit=5)
        
        story.append(Paragraph("INDICADORES CLAVE DE RENDIMIENTO", subtitle_style))
        kpi_data = [
            ['Indicador', 'Valor', 'Estado'],
            ['Ventas Totales', f"C$ {kpis['total_sales']:,.2f}", '✓ Pasativo' if kpis['sales_growth'] >= 0 else '⚠ Negativo'],
            ['Compras Totales', f"C$ {kpis['total_purchases']:,.2f}", '✓ Controlado' if kpis['purchases_growth'] <= 10 else '⚠ Alto'],
            ['Ganancia Neta', f"C$ {kpis['net_profit']:,.2f}", '✓ Rentable' if kpis['net_profit'] > 0 else '⚠ Pérdida'],
            ['Margen de Utilidad', f"{kpis['profit_margin']:.1f}%", '✓ Saludable' if kpis['profit_margin'] > 15 else '⚠ Bajo']
        ]
        
        kpi_table = Table(kpi_data, colWidths=[6*inch/3, 6*inch/3, 6*inch/3])
        kpi_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4361ee')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(kpi_table)
        story.append(Spacer(1, 20))
        
        story.append(Paragraph("TOP 5 PRODUCTOS MÁS VENDIDOS", subtitle_style))
        if top_products:
            product_data = [['#', 'Producto', 'Categoría', 'Cantidad', 'Ventas Totales']]
            for i, p in enumerate(top_products, 1):
                product_data.append([str(i), p['Nombre'], p['Categoria'], str(int(p['TotalVendido'])), f"C$ {p['TotalVentas']:,.2f}"])
            product_table = Table(product_data)
            product_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1cc88a')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(product_table)
        else:
            story.append(Paragraph("No hay datos de productos disponibles.", styles['Normal']))
            
        story.append(Spacer(1, 20))
        
        if grouped_transactions:
            story.append(Paragraph("REPORTE DETALLADO DE TRANSACCIONES DIARIAS", subtitle_style))
            trans_data = [['Fecha', 'Ingresos', 'Egresos', 'Balance', 'Tendencia']]
            for trans in grouped_transactions[:20]:
                trend = 'Positivo' if trans['balance'] > 0 else 'Negativo' if trans['balance'] < 0 else 'Neutral'
                trans_data.append([
                    trans['period'], f"C$ {trans['income']:,.2f}", f"C$ {trans['expense']:,.2f}",
                    f"C$ {trans['balance']:,.2f}", trend
                ])
            trans_table = Table(trans_data)
            trans_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f6c23e')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('ALIGN', (1, 1), (-2, -1), 'RIGHT'),
            ]))
            story.append(trans_table)

        story.append(Spacer(1, 30))
        footer_text = f"Reporte generado el {datetime.now().strftime('%d/%m/%Y a las %H:%M')}"
        story.append(Paragraph(footer_text, styles['Normal']))
        
        doc.build(story)
        buffer.seek(0)
        return buffer

    @staticmethod
    def generate_excel_report(filters):
        """Generar Excel Spreadsheet usando pandas"""
        buffer = BytesIO()
        kpis = ReporteService.get_kpis(filters)
        top_products = ReporteRepository.obtener_top_productos(filters, limit=20)
        transactions = ReporteService.get_transactions(filters)
        
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            kpi_df = pd.DataFrame([
                ['Ventas Totales', f"C$ {kpis['total_sales']:,.2f}"],
                ['Compras Totales', f"C$ {kpis['total_purchases']:,.2f}"],
                ['Ganancia Neta', f"C$ {kpis['net_profit']:,.2f}"],
                ['Margen de Utilidad', f"{kpis['profit_margin']:.1f}%"]
            ], columns=['Indicador', 'Valor'])
            kpi_df.to_excel(writer, sheet_name='KPIs', index=False)
            
            if top_products:
                pd.DataFrame(top_products).to_excel(writer, sheet_name='Top Productos', index=False)
                
            if transactions:
                # Quitamos la descripción concatenada larga si queremos
                pd.DataFrame(transactions).to_excel(writer, sheet_name='Transacciones', index=False)
                
        buffer.seek(0)
        return buffer

    @staticmethod
    def exportar_compras_excel(filtros):
        """Generador específico para el historial de compras en formato Excel"""
        from app.repositories.compra_repository import CompraRepository
        import io
        
        compras = CompraRepository.obtener_historial_compras(filtros)
        if not compras:
            return None
        
        compra_ids = [compra['IDCompra'] for compra in compras]
        
        # Obtener los detalles de los arreglos IDs
        detalles_totales = []
        for cid in compra_ids:
            detalles_compra = CompraRepository.obtener_detalles_compra(cid)
            for dc in detalles_compra:
                detalles_totales.append({
                    'ID Compra': cid,
                    'Producto': dc['Producto'],
                    'Proveedor': dc['Proveedor'],
                    'Sucursal': dc['Sucursal'],
                    'Cantidad': dc['Cantidad'],
                    'Subtotal': dc['Subtotal'],
                    'Precio Compra': dc['PrecioCompra']
                })
        
        # Transformar las compras para que matcheen la versión original de UI
        compras_formateadas = []
        for c in compras:
            compras_formateadas.append({
                'ID Compra': c['IDCompra'],
                'Fecha': c['Fecha'],
                'Total': c['Total'],
                'Proveedores': c['proveedores'],
                'Sucursales': c['sucursal']
            })

        df_compras = pd.DataFrame(compras_formateadas)
        df_detalles = pd.DataFrame(detalles_totales)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_compras.to_excel(writer, sheet_name='Compras', index=False)
            if not df_detalles.empty:
                df_detalles.to_excel(writer, sheet_name='Detalles', index=False)
            
            workbook = writer.book
            formato_moneda = workbook.add_format({'num_format': '$#,##0.00'})
            
            worksheet_compras = writer.sheets['Compras']
            worksheet_compras.set_column('C:C', 12, formato_moneda)
            if 'Detalles' in writer.sheets:
                worksheet_detalles = writer.sheets['Detalles']
                worksheet_detalles.set_column('F:G', 12, formato_moneda)
                
            for worksheet_name in writer.sheets:
                ws = writer.sheets[worksheet_name]
                for i, col in enumerate(df_compras.columns if worksheet_name == 'Compras' else df_detalles.columns):
                    ws.set_column(i, i, 15)

        output.seek(0)
        return output
