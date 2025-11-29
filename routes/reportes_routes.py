from flask import Blueprint, render_template, flash, send_file
from flask_login import login_required
from extensions import db
from models.clientes import Cliente, EstadoMembresia
from models.pagos import Pago, EstadoPago
from models.asistencias import Asistencia
from routes.decoradores import roles_required

from datetime import date
from sqlalchemy import extract, func

# PDF
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics import renderPDF


reportes_bp = Blueprint("reportes", __name__, url_prefix="/reportes")


# ===========================================================
# 📊 REPORTE GENERAL (DASHBOARD HTML)
# ===========================================================
@reportes_bp.route("/general")
@login_required
@roles_required("ADMIN")
def reporte_general():
    try:
        # CLIENTES
        total_clientes = db.session.query(func.count(Cliente.id)).scalar()
        activos = db.session.query(func.count()).filter(
            Cliente.estado_membresia == EstadoMembresia.ACTIVO
        ).scalar()
        vencidos = db.session.query(func.count()).filter(
            Cliente.estado_membresia == EstadoMembresia.VENCIDO
        ).scalar()

        # PAGOS
        total_pagos = db.session.query(func.count(Pago.id)).scalar()
        pagos_validados = Pago.query.filter_by(estado=EstadoPago.VALIDADO).count()
        pagos_rechazados = Pago.query.filter_by(estado=EstadoPago.RECHAZADO).count()
        pagos_pendientes = Pago.query.filter_by(estado=EstadoPago.PENDIENTE).count()

        # ASISTENCIAS — MES ACTUAL
        hoy = date.today()
        asistencias_mes = Asistencia.query.filter(
            extract("month", Asistencia.fecha) == hoy.month,
            extract("year", Asistencia.fecha) == hoy.year
        ).count()

        # ASISTENCIAS — POR DÍA DE LA SEMANA
        asistencias_por_dia = db.session.query(
            extract("dow", Asistencia.fecha).label("dia_semana"),
            func.count(Asistencia.id).label("total")
        ).filter(
            extract("month", Asistencia.fecha) == hoy.month,
            extract("year", Asistencia.fecha) == hoy.year
        ).group_by("dia_semana").all()

        dias_semana = ["Domingo","Lunes","Martes","Miércoles","Jueves","Viernes","Sábado"]
        asistencias_dict = {dias_semana[int(r.dia_semana)]: r.total for r in asistencias_por_dia}

    except Exception as e:
        flash(f"Error generando reporte: {e}", "danger")
        asistencias_dict = {}
        total_clientes = activos = vencidos = 0
        total_pagos = pagos_validados = pagos_rechazados = pagos_pendientes = asistencias_mes = 0    

    return render_template(
        "admin/reporte_general.html",
        total_clientes=total_clientes, activos=activos, vencidos=vencidos,
        total_pagos=total_pagos, pagos_validados=pagos_validados,
        pagos_rechazados=pagos_rechazados, pagos_pendientes=pagos_pendientes,
        asistencias_mes=asistencias_mes,
        asistencias_por_dia=asistencias_dict
    )


# ===========================================================
# 🧾 DESCARGAR PDF — REPORTE COMPLETO
# ===========================================================
@reportes_bp.route("/descargar/pdf")
@login_required
@roles_required("ADMIN")
def descargar_general_pdf():
    
    # Se consulta solo lo necesario — liviano y rápido
    stats = {
        "total_clientes": Cliente.query.count(),
        "activos": Cliente.query.filter_by(estado_membresia=EstadoMembresia.ACTIVO).count(),
        "vencidos": Cliente.query.filter_by(estado_membresia=EstadoMembresia.VENCIDO).count(),
        "total_pagos": Pago.query.count(),
        "pagos_validados": Pago.query.filter_by(estado=EstadoPago.VALIDADO).count(),
        "pagos_rechazados": Pago.query.filter_by(estado=EstadoPago.RECHAZADO).count(),
        "pagos_pendientes": Pago.query.filter_by(estado=EstadoPago.PENDIENTE).count(),
    }

    hoy = date.today()
    asistencias_mes = Asistencia.query.filter(
        extract("month", Asistencia.fecha) == hoy.month,
        extract("year", Asistencia.fecha) == hoy.year
    ).count()

    # Agrupación por día de semana
    dias_semana = ["Domingo","Lunes","Martes","Miércoles","Jueves","Viernes","Sábado"]
    asistencias_por_dia = Asistencia.query.with_entities(
        extract("dow", Asistencia.fecha).label("dia"), func.count()
    ).filter(
        extract("month", Asistencia.fecha) == hoy.month,
        extract("year", Asistencia.fecha) == hoy.year
    ).group_by("dia").all()

    asistencias_dict = {dias_semana[int(k)]: v for k,v in asistencias_por_dia}
    pagos = Pago.query.order_by(Pago.fecha_pago.desc()).limit(20).all()

    # ========= GENERACIÓN DEL PDF =========
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.setTitle("Reporte General HITO Sport")

    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(50, 760, "📄 Reporte General — HITO SPORT")
    pdf.setFont("Helvetica", 12)
    y = 730

    # CLIENTES
    pdf.drawString(50, y, f"Total Clientes: {stats['total_clientes']}")
    pdf.drawString(250, y, f"Activos: {stats['activos']}")
    pdf.drawString(380, y, f"Vencidos: {stats['vencidos']}")
    y -= 30

    # PAGOS
    pdf.drawString(50, y, f"Total Pagos: {stats['total_pagos']}")
    pdf.drawString(250, y, f"Validados: {stats['pagos_validados']}")
    pdf.drawString(380, y, f"Pendientes: {stats['pagos_pendientes']}")
    y -= 30

    # ASISTENCIAS
    pdf.drawString(50, y, f"Asistencias este mes: {asistencias_mes}")
    y -= 40

    # 🔥 GRÁFICO DE ASISTENCIAS (barras)
    drawing = Drawing(450, 150)
    max_val = max(asistencias_dict.values() or [1])
    pos_x = 20

    for dia, total in asistencias_dict.items():
        bar_height = (total / max_val) * 120
        drawing.add(Rect(pos_x, 10, 40, bar_height, fillColor=colors.HexColor("#0077FF")))
        drawing.add(String(pos_x, 0, dia[:3], fontSize=8))
        drawing.add(String(pos_x, bar_height+15, str(total), fontSize=9))
        pos_x += 55

    renderPDF.draw(drawing, pdf, 50, y-140)
    y -= 170

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(50, y, "Pagos Recientes (máx 20)")
    y -= 20
    pdf.setFont("Helvetica", 10)

    for p in pagos:
        if y < 60:
            pdf.showPage()
            y = 750
            pdf.setFont("Helvetica", 10)

        color = {"PENDIENTE": colors.orange, "VALIDADO": colors.green, "RECHAZADO": colors.red}[p.estado.value]
        pdf.setFillColor(color)
        pdf.drawString(50, y, f"{p.cliente.nombre} — {p.tipo.value} — {p.monto} — {p.estado.value}")
        pdf.setFillColor(colors.black)
        y -= 15

    pdf.save()
    buffer.seek(0)

    return send_file(buffer,
        as_attachment=True,
        download_name="reporte_general_HITO.pdf",
        mimetype="application/pdf"
    )
