from flask import Blueprint, render_template, flash, send_file, redirect, url_for
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

# 🔹 Dependencia API
import requests


reportes_bp = Blueprint("reportes", __name__, url_prefix="/reportes")


# ===========================================================
# 📊 REPORTE GENERAL (DASHBOARD HTML EN Bs)
# ===========================================================
@reportes_bp.route("/general")
@login_required
@roles_required("ADMIN")
def reporte_general():

    total_clientes = Cliente.query.count()
    activos = Cliente.query.filter_by(estado_membresia=EstadoMembresia.ACTIVO).count()
    vencidos = Cliente.query.filter_by(estado_membresia=EstadoMembresia.VENCIDO).count()

    total_pagos = Pago.query.count()
    pagos_validados = Pago.query.filter_by(estado=EstadoPago.VALIDADO).count()
    pagos_rechazados = Pago.query.filter_by(estado=EstadoPago.RECHAZADO).count()
    pagos_pendientes = Pago.query.filter_by(estado=EstadoPago.PENDIENTE).count()

    pagos_validados_lista = Pago.query.filter_by(estado=EstadoPago.VALIDADO).all()
    total_ganancias = sum(p.monto for p in pagos_validados_lista)

    hoy = date.today()
    asistencias_mes = Asistencia.query.filter(
        extract("month", Asistencia.fecha) == hoy.month,
        extract("year", Asistencia.fecha) == hoy.year
    ).count()

    meses = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"]
    montos_validados = []

    for m in range(1, 13):
        total_mes = db.session.query(func.sum(Pago.monto)).filter(
            Pago.estado == EstadoPago.VALIDADO,
            extract("month", Pago.fecha_pago) == m
        ).scalar() or 0

        montos_validados.append(float(total_mes))

    return render_template(
        "admin/reporte_general.html",
        total_clientes=total_clientes,
        activos=activos,
        vencidos=vencidos,
        total_pagos=total_pagos,
        pagos_validados=pagos_validados,
        pagos_rechazados=pagos_rechazados,
        pagos_pendientes=pagos_pendientes,
        total_ganancias=total_ganancias,
        asistencias_mes=asistencias_mes,
        meses=meses,
        montos_validados=montos_validados
    )


# ===========================================================
# 🧾 PDF — EN BOLÍVARES
# ===========================================================
@reportes_bp.route("/descargar/pdf_bs")
@login_required
@roles_required("ADMIN")
def descargar_general_pdf_bs():

    hoy = date.today()
    meses = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"]

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.setTitle("Reporte General - Bs")

    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(50, 760, "REPORTE GENERAL (BS)")
    y = 720

    total_anual = 0

    pdf.setFont("Helvetica", 12)
    for m in range(1, 13):
        total_mes = db.session.query(func.sum(Pago.monto)).filter(
            Pago.estado == EstadoPago.VALIDADO,
            extract("month", Pago.fecha_pago) == m,
            extract("year", Pago.fecha_pago) == hoy.year
        ).scalar() or 0

        pdf.drawString(50, y, f"{meses[m-1]}: {total_mes:.2f} Bs")
        total_anual += total_mes
        y -= 18

        if y < 60:
            pdf.showPage()
            y = 760
            pdf.setFont("Helvetica", 12)

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, y, f"TOTAL ANUAL: {total_anual:.2f} Bs")

    pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="reporte_general_bs.pdf",
        mimetype="application/pdf"
    )


# ===========================================================
# 🧾 PDF — EN DÓLARES
# ===========================================================
@reportes_bp.route("/descargar/pdf_usd")
@login_required
@roles_required("ADMIN")
def descargar_general_pdf_usd():

    try:
        res = requests.get("https://api.exchangerate-api.com/v4/latest/USD")
        data = res.json()
        tasa = data["rates"]["VES"]
    except:
        flash("❌ No se pudo obtener la tasa BCV.", "danger")
        return redirect(url_for("reportes.reporte_general"))

    hoy = date.today()
    meses = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"]

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.setTitle("Reporte General - USD")

    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(50, 760, "REPORTE GENERAL (USD)")
    y = 720

    pdf.setFont("Helvetica", 12)
    pdf.drawString(50, y, f"Tasa BCV: 1 USD = {tasa:.2f} Bs")
    y -= 30

    total_anual_bs = 0

    for m in range(1, 13):
        total_mes_bs = db.session.query(func.sum(Pago.monto)).filter(
            Pago.estado == EstadoPago.VALIDADO,
            extract("month", Pago.fecha_pago) == m,
            extract("year", Pago.fecha_pago) == hoy.year
        ).scalar() or 0

        usd = total_mes_bs / tasa
        pdf.drawString(50, y, f"{meses[m-1]}: {usd:.2f} USD")
        total_anual_bs += total_mes_bs
        y -= 18

        if y < 60:
            pdf.showPage()
            y = 760
            pdf.setFont("Helvetica", 12)

    total_usd = total_anual_bs / tasa
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, y, f"TOTAL ANUAL: {total_usd:.2f} USD")

    pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="reporte_general_usd.pdf",
        mimetype="application/pdf"
    )
