from datetime import datetime, date, time, timedelta, timezone
from flask import Blueprint, render_template, flash
from flask_login import login_required
from sqlalchemy import func

# Decorador
from routes.decoradores import roles_required

# Modelos
from models.clientes import Cliente, EstadoMembresia
from models.pagos import Pago, EstadoPago
from models.asistencias import Asistencia
from extensions import db

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# ---------------------------------------------------
# Dashboard - estadísticas clave
# ---------------------------------------------------
@admin_bp.route("/dashboard")
@login_required
@roles_required("ADMIN")
def dashboard():
    """
    Dashboard con métricas clave.
    Se usan consultas con func.count() para mayor eficiencia en bases grandes.
    """

    try:
        # --- Clientes ---
        clientes_activos = db.session.query(func.count(Cliente.id)).filter(
            Cliente.estado_membresia == EstadoMembresia.ACTIVO
        ).scalar()

        clientes_vencidos = db.session.query(func.count(Cliente.id)).filter(
            Cliente.estado_membresia == EstadoMembresia.VENCIDO
        ).scalar()

        # --- Pagos pendientes ---
        pagos_pendientes = db.session.query(func.count(Pago.id)).filter(
            Pago.estado == EstadoPago.PENDIENTE
        ).scalar()

        # --- Asistencias de hoy ---
        hoy_start = datetime.combine(date.today(), time.min).replace(tzinfo=timezone.utc)
        hoy_end = hoy_start + timedelta(days=1)

        hoy_iso = datetime.utcnow().date().isoformat()
        asistencias_hoy = db.session.query(func.count(Asistencia.id)).filter(
        db.func.date(Asistencia.fecha) == hoy_iso
            ).scalar()

    except Exception as e:
        flash(f"Error al generar métricas: {str(e)}", "danger")
        clientes_activos = clientes_vencidos = pagos_pendientes = asistencias_hoy = 0

    return render_template(
        "admin/dashboard.html",
        clientes_activos=clientes_activos,
        clientes_vencidos=clientes_vencidos,
        pagos_pendientes=pagos_pendientes,
        asistencias_hoy=asistencias_hoy
    )