from flask import Blueprint, render_template, flash, send_file
from flask_login import login_required
from extensions import db
from models.clientes import Cliente, EstadoMembresia
from models.pagos import Pago, EstadoPago
from models.asistencias import Asistencia
from routes.decoradores import roles_required
from datetime import date
from sqlalchemy import extract, func

#Para generar reportes
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics import renderPDF


reportes_bp = Blueprint("reportes", __name__, url_prefix="/reportes")

# ---------------------------
# Reportes globales (solo admin)
# ---------------------------
@reportes_bp.route("/general")
@login_required
@roles_required("ADMIN")
def reporte_general():
    try:
        # --- Clientes ---
        total_clientes = db.session.query(func.count(Cliente.id)).scalar()
        activos = db.session.query(func.count(Cliente.id)).filter(
            Cliente.estado_membresia == EstadoMembresia.ACTIVO
        ).scalar()
        vencidos = db.session.query(func.count(Cliente.id)).filter(
            Cliente.estado_membresia == EstadoMembresia.VENCIDO
        ).scalar()

        # --- Pagos ---
        total_pagos = db.session.query(func.count(Pago.id)).scalar()
        pagos_validados = db.session.query(func.count(Pago.id)).filter(
            Pago.estado == EstadoPago.VALIDADO
        ).scalar()
        pagos_rechazados = db.session.query(func.count(Pago.id)).filter(
            Pago.estado == EstadoPago.RECHAZADO
        ).scalar()
        pagos_pendientes = db.session.query(func.count(Pago.id)).filter(
            Pago.estado == EstadoPago.PENDIENTE
        ).scalar()

        # --- Asistencias del mes ---
        hoy = date.today()
        asistencias_mes = db.session.query(func.count(Asistencia.id)).filter(
            extract("month", Asistencia.fecha) == hoy.month,
            extract("year", Asistencia.fecha) == hoy.year
        ).scalar()

        # --- Asistencias por día de la semana ---
        asistencias_por_dia = db.session.query(
            extract("dow", Asistencia.fecha).label("dia_semana"),
            func.count(Asistencia.id).label("total")
        ).filter(
            extract("month", Asistencia.fecha) == hoy.month,
            extract("year", Asistencia.fecha) == hoy.year
        ).group_by("dia_semana").all()

        # Mapear números de día a nombres
        dias = ["Domingo", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]
        asistencias_dict = {dias[int(r.dia_semana)]: r.total for r in asistencias_por_dia}

    except Exception as e:
        flash(f"Error al generar reporte: {str(e)}", "danger")
        # valores por defecto en caso de error
        total_clientes = activos = vencidos = 0
        total_pagos = pagos_validados = pagos_rechazados = pagos_pendientes = 0
        asistencias_mes = 0
        asistencias_dict = {}

    return render_template(
        "admin/reporte_general.html",
        total_clientes=total_clientes,
        activos=activos,
        vencidos=vencidos,
        total_pagos=total_pagos,
        pagos_validados=pagos_validados,
        pagos_rechazados=pagos_rechazados,
        pagos_pendientes=pagos_pendientes,
        asistencias_mes=asistencias_mes,
        asistencias_por_dia=asistencias_dict
    )


@reportes_bp.route("/descargar/pdf")
@login_required
@roles_required("ADMIN")
def descargar_general_pdf():
    # --- Datos ---
    total_clientes = db.session.query(func.count(Cliente.id)).scalar()
    activos = db.session.query(func.count(Cliente.id)).filter(
        Cliente.estado_membresia == EstadoMembresia.ACTIVO
    ).scalar()
    vencidos = db.session.query(func.count(Cliente.id)).filter(
        Cliente.estado_membresia == EstadoMembresia.VENCIDO
    ).scalar()

    total_pagos = db.session.query(func.count(Pago.id)).scalar()
    pagos_validados = db.session.query(func.count(Pago.id)).filter(
        Pago.estado == EstadoPago.VALIDADO
    ).scalar()
    pagos_rechazados = db.session.query(func.count(Pago.id)).filter(
        Pago.estado == EstadoPago.RECHAZADO
    ).scalar()
    pagos_pendientes = db.session.query(func.count(Pago.id)).filter(
        Pago.estado == EstadoPago.PENDIENTE
    ).scalar()

    hoy = date.today()
    asistencias_mes = db.session.query(func.count(Asistencia.id)).filter(
        extract("month", Asistencia.fecha) == hoy.month,
        extract("year", Asistencia.fecha) == hoy.year
    ).scalar()

    asistencias_por_dia = db.session.query(
        extract("dow", Asistencia.fecha).label("dia_semana"),
        func.count(Asistencia.id).label("total")
    ).filter(
        extract("month", Asistencia.fecha) == hoy.month,
        extract("year", Asistencia.fecha) == hoy.year
    ).group_by("dia_semana").all()

    dias = ["Domingo", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]
    asistencias_dict = {dias[int(r.dia_semana)]: r.total for r in asistencias_por_dia}

    pagos = Pago.query.order_by(Pago.fecha_pago.desc()).all()

    # --- Crear PDF ---
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.setTitle("Reporte General - Admin")

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, "Reporte General - Admin")
    c.setFont("Helvetica", 12)
    y = 720

    # --- Clientes ---
    c.drawString(50, y, f"Total Clientes: {total_clientes}")
    y -= 20
    c.drawString(50, y, f"Clientes Activos: {activos}")
    y -= 20
    c.drawString(50, y, f"Clientes Vencidos: {vencidos}")
    y -= 30

    # --- Pagos ---
    c.drawString(50, y, f"Total Pagos: {total_pagos}")
    y -= 20
    c.drawString(50, y, f"Pagos Validados: {pagos_validados}")
    y -= 20
    c.drawString(50, y, f"Pagos Rechazados: {pagos_rechazados}")
    y -= 20
    c.drawString(50, y, f"Pagos Pendientes: {pagos_pendientes}")
    y -= 30

    # --- Asistencias ---
    c.drawString(50, y, f"Asistencias este mes: {asistencias_mes}")
    y -= 20

    # --- Gráfico de asistencias ---
    drawing = Drawing(400, 150)
    max_asistencias = max(asistencias_dict.values() or [1])
    barra_ancho = 40
    espacio = 10
    x = 50

    for dia, total in asistencias_dict.items():
        altura = 100 * (total / max_asistencias)  # escala
        rect = Rect(x, 0, barra_ancho, altura, fillColor=colors.blue)
        drawing.add(rect)
        drawing.add(String(x, -15, dia[:3], fontSize=8))
        drawing.add(String(x, altura + 2, str(total), fontSize=8))
        x += barra_ancho + espacio

    renderPDF.draw(drawing, c, 50, y - 120)
    y -= 160

    # --- Tabla de pagos ---
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Pagos recientes:")
    y -= 20
    c.setFont("Helvetica", 10)
    for pago in pagos[:20]:  # solo los 20 más recientes
        estado_color = {"PENDIENTE": colors.orange, "VALIDADO": colors.green, "RECHAZADO": colors.red}[pago.estado.value]
        c.setFillColor(estado_color)
        c.drawString(50, y, f"{pago.cliente.nombre} - {pago.tipo.value} - {pago.monto} - {pago.estado.value}")
        y -= 15
        c.setFillColor(colors.black)
        if y < 50:
            c.showPage()
            y = 750

    c.showPage()
    c.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="reporte_general.pdf", mimetype="application/pdf")
