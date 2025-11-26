from flask import Blueprint, render_template, flash
from flask_login import login_required
from extensions import db
from models.clientes import Cliente, EstadoMembresia
from models.pagos import Pago, EstadoPago
from models.asistencias import Asistencia
from routes.decoradores import roles_required
from datetime import date
from sqlalchemy import extract, func

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