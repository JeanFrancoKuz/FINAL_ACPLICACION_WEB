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
# 📊 REPORTE GENERAL (Dashboard HTML)
# ===========================================================
@reportes_bp.route("/general")
@login_required
@roles_required("ADMIN")
def reporte_general():
    try:
        # CLIENTES
        total_clientes = Cliente.query.count()
        activos = Cliente.query.filter_by(estado_membresia=EstadoMembresia.ACTIVO).count()
        vencidos = Cliente.query.filter_by(estado_membresia=EstadoMembresia.VENCIDO).count()

        # PAGOS
        total_pagos = Pago.query.count()
        pagos_validados = Pago.query.filter_by(estado=EstadoPago.VALIDADO).count()
        pagos_rechazados = Pago.query.filter_by(estado=EstadoPago.RECHAZADO).count()
        pagos_pendientes = Pago.query.filter_by(estado=EstadoPago.PENDIENTE).count()

        # 🔹 TOTAL DE GANANCIAS (solo pagos validados)
        pagos_validados_lista = Pago.query.filter_by(estado=EstadoPago.VALIDADO).all()
        total_ganancias = sum(p.monto for p in pagos_validados_lista)

        # ASISTENCIAS — MES ACTUAL
        hoy = date.today()
        asistencias_mes = Asistencia.query.filter(
            extract("month", Asistencia.fecha) == hoy.month,
            extract("year", Asistencia.fecha) == hoy.year
        ).count()

        # ASISTENCIAS — POR DÍA
        asistencias_por_dia_raw = db.session.query(
            extract("dow", Asistencia.fecha).label("dia_semana"),
            func.count(Asistencia.id)
        ).filter(
            extract("month", Asistencia.fecha) == hoy.month,
            extract("year", Asistencia.fecha) == hoy.year
        ).group_by("dia_semana").all()

        dias_semana = ["Domingo","Lunes","Martes","Miércoles","Jueves","Viernes","Sábado"]
        asistencias_por_dia = {dias_semana[int(dia)]: total for dia, total in asistencias_por_dia_raw}

        # 🔹 GRÁFICO mensual de pagos validados
        meses = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"]
        montos_validados = []

        for m in range(1, 12 + 1):
            total_mes = db.session.query(func.sum(Pago.monto)).filter(
                Pago.estado == EstadoPago.VALIDADO,
                extract("month", Pago.fecha_pago) == m
            ).scalar() or 0
            montos_validados.append(float(total_mes))

    except Exception as e:
        flash(f"Error generando reporte: {e}", "danger")
        return render_template("admin/reporte_general.html",
            total_clientes=0, activos=0, vencidos=0,
            total_pagos=0, pagos_validados=0, pagos_rechazados=0, pagos_pendientes=0,
            total_ganancias=0,
            asistencias_mes=0, asistencias_por_dia={},
            meses=[], montos_validados=[]
        )

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
        asistencias_por_dia=asistencias_por_dia,

        meses=meses,
        montos_validados=montos_validados
    )


# ===========================================================
# 🧾 DESCARGAR PDF — Reporte General
# ===========================================================
@reportes_bp.route("/descargar/pdf")
@login_required
@roles_required("ADMIN")
def descargar_general_pdf():
    
    # ======== CONSULTAS BÁSICAS =========
    stats = {
        "total_clientes": Cliente.query.count(),
        "activos": Cliente.query.filter_by(estado_membresia=EstadoMembresia.ACTIVO).count(),
        "vencidos": Cliente.query.filter_by(estado_membresia=EstadoMembresia.VENCIDO).count(),
        "total_pagos": Pago.query.count(),
        "pagos_validados": Pago.query.filter_by(estado=EstadoPago.VALIDADO).count(),
        "pagos_rechazados": Pago.query.filter_by(estado=EstadoPago.RECHAZADO).count(),
        "pagos_pendientes": Pago.query.filter_by(estado=EstadoPago.PENDIENTE).count(),
    }

    # Fechas
    hoy = date.today()

    # ======== PAGOS POR MES =========
    meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]

    pagos_por_mes = {}
    total_anual = 0

    for m in range(1, 12+1):
        pagos_mes = Pago.query.filter(
            Pago.estado == EstadoPago.VALIDADO,
            extract("month", Pago.fecha_pago) == m,
            extract("year", Pago.fecha_pago) == hoy.year
        ).all()

        total_mes = sum(p.monto for p in pagos_mes)
        pagos_por_mes[m] = {"total": total_mes, "lista": pagos_mes}
        total_anual += total_mes

    # ======== ASISTENCIAS POR MES =========
    asistencias_por_mes = {}

    for m in range(1, 12+1):
        asistencias = Asistencia.query.filter(
            extract("month", Asistencia.fecha) == m,
            extract("year", Asistencia.fecha) == hoy.year
        ).all()

        asistencias_por_mes[m] = len(asistencias)

    # ======== GENERACIÓN DEL PDF =========
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.setTitle("Reporte General HITO Sport")

    # Título principal
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(50, 760, "REPORTE GENERAL - HITO SPORT")
    pdf.setFont("Helvetica", 12)
    y = 730

    # ======== RESUMEN GENERAL =========
    pdf.drawString(50, y, f"Total Clientes: {stats['total_clientes']}")
    pdf.drawString(250, y, f"Activos: {stats['activos']}")
    pdf.drawString(380, y, f"Vencidos: {stats['vencidos']}")
    y -= 25

    pdf.drawString(50, y, f"Total Pagos: {stats['total_pagos']}")
    pdf.drawString(250, y, f"Validados: {stats['pagos_validados']}")
    pdf.drawString(380, y, f"Pendientes: {stats['pagos_pendientes']}")
    y -= 40

    # ======== PAGOS POR MES =========
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, y, "📌 PAGOS POR MES")
    y -= 20
    pdf.setFont("Helvetica", 11)

    for m in range(1, 13):

        nombre_mes = meses[m-1]
        total_mes = pagos_por_mes[m]["total"]
        lista_pagos = pagos_por_mes[m]["lista"]

        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(50, y, f"{nombre_mes} - Total: ${total_mes:.2f}")
        y -= 18

        pdf.setFont("Helvetica", 10)

        if not lista_pagos:
            pdf.drawString(60, y, "No hubo pagos este mes.")
            y -= 18
        else:
            for p in lista_pagos:
                linea = f"- {p.fecha_pago.strftime('%d/%m/%Y')} | {p.cliente.nombre} | ${p.monto:.2f}"
                pdf.drawString(60, y, linea)
                y -= 15

                # Nueva página si se llena
                if y < 60:
                    pdf.showPage()
                    y = 750

        y -= 8

        # Saltar de página entre meses largos
        if y < 80:
            pdf.showPage()
            y = 750

    # ======== TOTAL ANUAL =========
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, y, f"💰 TOTAL ANUAL DE INGRESOS: ${total_anual:.2f}")
    y -= 40

    # ======== ASISTENCIAS POR MES =========
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, y, "📌 ASISTENCIAS POR MES")
    y -= 25
    pdf.setFont("Helvetica", 11)

    for m in range(1, 13):
        pdf.drawString(
            50, y,
            f"{meses[m-1]}: {asistencias_por_mes[m]} asistencias"
        )
        y -= 18

        if y < 60:
            pdf.showPage()
            y = 750

    pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="reporte_general_completo_HITO.pdf",
        mimetype="application/pdf"
    )
