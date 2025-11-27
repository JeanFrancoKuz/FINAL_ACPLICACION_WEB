from datetime import datetime, date, time, timedelta, timezone
from flask import Blueprint, render_template, flash, redirect, url_for
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

# ---------------------------
# enviar mensaje
# ---------------------------
@admin_bp.route("/enviar_mensaje/<int:cliente_id>")
@login_required
@roles_required("ADMIN")
def enviar_mensaje(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)

    if cliente.estado_membresia != EstadoMembresia.VENCIDO:
        flash("Solo se puede enviar mensaje a clientes con membresía vencida.", "warning")
        return redirect(url_for("cliente.lista_clientes"))

    # Construir el mensaje
    mensaje = f"""
Hola {cliente.nombre},

Notamos que tu membresía en HITO ALL SPORT ha vencido el {cliente.membresia_vencimiento.strftime('%d-%m-%Y')}.
Te invitamos a renovarla para continuar con tus entrenamientos y beneficios.

Para renovar tu membresía, por favor contáctanos al {cliente.telefono or 'correo: ' + cliente.correo} o ingresa a tu perfil y realiza el pago correspondiente.

¡Te esperamos!
HITO ALL SPORT
"""

    # Simulación de envío
    if cliente.telefono:
        print(f"[DEBUG] Mensaje enviado a {cliente.telefono}:\n{mensaje}")
    else:
        print(f"[DEBUG] Mensaje enviado a {cliente.correo}:\n{mensaje}")

    flash(f"Mensaje de recordatorio enviado a {cliente.nombre}.", "success")
    return redirect(url_for("cliente.lista_clientes"))
