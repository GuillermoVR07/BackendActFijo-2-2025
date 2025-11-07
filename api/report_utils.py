# api/report_utils.py

import io
import logging
from django.http import HttpResponse
from openpyxl import Workbook
from openpyxl.styles import Font
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch

# Configurar logger (opcional pero bueno para depurar)
logger = logging.getLogger(__name__)

def create_excel_report(queryset):
    """Genera un HttpResponse con el reporte de activos en formato Excel."""
    try:
        logger.debug("create_excel_report: Starting Excel generation...")
        buffer = io.BytesIO()
        wb = Workbook()
        ws = wb.active
        ws.title = "Reporte de Activos"

        # Encabezados
        headers = ["Nombre", "Código Interno", "Ubicación", "Categoría", "Departamento", "Fecha Adquisición", "Valor Actual (Bs.)", "Estado"]
        ws.append(headers)
        for cell in ws[1]: # Poner encabezados en negrita
            cell.font = Font(bold=True)

        # Añadir datos
        for activo in queryset:
            ws.append([
                activo.nombre,
                activo.codigo_interno,
                activo.ubicacion.nombre if activo.ubicacion else 'N/A',
                activo.categoria.nombre if activo.categoria else 'N/A',
                activo.departamento.nombre if hasattr(activo, 'departamento') and activo.departamento else 'N/A', # Si departamento está en queryset
                activo.fecha_adquisicion,
                activo.valor_actual,
                activo.estado.nombre if activo.estado else 'N/A'
            ])

        # Ajustar ancho de columnas (opcional)
        for col in ws.columns:
             max_length = 0
             column = col[0].column_letter # Get the column name
             for cell in col:
                 try: # Necesario para manejar celdas vacías o tipos mixtos
                     if len(str(cell.value)) > max_length:
                         max_length = len(str(cell.value))
                 except:
                     pass
             adjusted_width = (max_length + 2)
             ws.column_dimensions[column].width = adjusted_width

        wb.save(buffer)
        buffer.seek(0)
        logger.debug(f"create_excel_report: Buffer size = {buffer.getbuffer().nbytes} bytes.")

        response = HttpResponse(
            buffer,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="reporte_activos.xlsx"'
        logger.info("create_excel_report: Response created successfully.")
        return response
    except Exception as e:
         logger.error(f"create_excel_report: Error during generation: {e}", exc_info=True)
         # Re-lanzar para que la vista lo capture como 500
         raise

def create_pdf_report(queryset):
    """Genera un HttpResponse con el reporte de activos en formato PDF."""
    try:
        logger.debug("create_pdf_report: Starting PDF generation...")
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        # Título y configuración inicial
        page_num = 1
        y_position = height - inch # Posición Y actual

        def draw_headers(canvas_obj, y_pos):
            canvas_obj.setFont('Helvetica-Bold', 10)
            x_pos = inch
            headers = ["Nombre", "Código", "Ubicación", "Categoría", "Depto", "Fecha Adq.", "Valor", "Estado"]
            # Ajustar anchos para incluir departamento
            col_widths = [1.8*inch, 0.7*inch, 1.0*inch, 0.9*inch, 0.8*inch, 0.7*inch, 0.7*inch, 0.9*inch]
            for i, header in enumerate(headers):
                canvas_obj.drawString(x_pos, y_pos, header)
                x_pos += col_widths[i]
            canvas_obj.line(inch, y_pos - 0.1 * inch, width - inch, y_pos - 0.1 * inch)
            return y_pos - 0.25 * inch, col_widths # Devolver nueva Y y anchos

        def draw_footer(canvas_obj, page_number):
             canvas_obj.setFont('Helvetica', 8)
             canvas_obj.drawString(inch, 0.75 * inch, f"Página {page_number}")
             canvas_obj.drawRightString(width - inch, 0.75 * inch, "Reporte Generado Automáticamente")


        # Título primera página
        p.setFont('Helvetica-Bold', 16)
        p.drawString(inch, y_position, "Reporte de Activos Fijos")
        y_position -= 0.5 * inch

        # Encabezados primera página
        y_position, column_widths = draw_headers(p, y_position)
        draw_footer(p, page_num)

        # Datos
        p.setFont('Helvetica', 9)
        line_height = 0.25 * inch
        for activo in queryset:
            # Salto de página si no hay espacio
            if y_position < inch + line_height: # Dejar espacio para el footer
                p.showPage()
                page_num += 1
                y_position = height - inch # Reiniciar Y
                y_position, column_widths = draw_headers(p, y_position) # Redibujar headers
                draw_footer(p, page_num) # Redibujar footer
                p.setFont('Helvetica', 9) # Volver a fuente normal

            # Preparar datos fila
            data = [
                activo.nombre[:22] + '...' if len(activo.nombre) > 22 else activo.nombre,
                activo.codigo_interno,
                activo.ubicacion.nombre[:14] if activo.ubicacion else 'N/A',
                activo.categoria.nombre[:12] if activo.categoria else 'N/A',
                activo.departamento.nombre[:10] if hasattr(activo, 'departamento') and activo.departamento else 'N/A',
                str(activo.fecha_adquisicion),
                f"{activo.valor_actual:.2f}", # Formatear valor
                activo.estado.nombre if activo.estado else 'N/A'
            ]
            x_position = inch
            for i, item in enumerate(data):
                p.drawString(x_position, y_position, str(item))
                x_position += column_widths[i]
            y_position -= line_height

        p.save() # Guarda el contenido PDF en el buffer
        buffer.seek(0)
        logger.debug(f"create_pdf_report: Buffer size = {buffer.getbuffer().nbytes} bytes.")

        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="reporte_activos.pdf"'
        logger.info("create_pdf_report: Response created successfully.")
        return response
    except Exception as e:
         logger.error(f"create_pdf_report: Error during generation: {e}", exc_info=True)
         raise