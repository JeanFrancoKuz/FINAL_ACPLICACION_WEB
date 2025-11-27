from datetime import datetime, date, time, timedelta, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app
from flask_login import login_required, current_user

# Decorador
from routes.decoradores import roles_required

# Modelos
from extensions import db
from models.asistencias import Asistencia
from models.clientes import Cliente

asistencia_bp = Blueprint("asistencia", __name__, url_prefix="/asistencias")

# ---------------------------------
# 1️Lista de asistencias (ADMIN only)
# ---------------------------------
@asistencia_bp.route("/lista")
@login_required
@roles_required("ADMIN")
def lista_asistencias():
    """
    Lista paginada de todas las asistencias (solo rol ADMIN).
    """
    page_number = request.args.get("page", 1, type=int)
    per_page = 20
    asistencias = Asistencia.query.order_by(
        Asistencia.fecha.desc()
    ).paginate(page_number, per_page, error_out=False)

    return render_template(
        "admin/lista_asistencias.html",
        asistencias=asistencias,
    )

# ---------------------------------
#Registrar asistencia (cliente)
# ---------------------------------
@asistencia_bp.route("/registrar", methods=["POST"])
@login_required
def registrar_asistencia():
    """
    Registra la asistencia del cliente autenticado en la fecha/hora actual.
    Se bloquea duplicados por día: solo una asistencia por día.
    """

    # Validar que el usuario tenga un cliente asociado
    if not current_user.cliente:
        flash("Tu usuario no está vinculado a un cliente.", "danger")
        return redirect(url_for("index"))

    cliente = current_user.cliente

# Evitar duplicados comparando la fecha (sin hora)
    hoy_iso = datetime.utcnow().date().isoformat()
    existente = Asistencia.query.filter(
        Asistencia.cliente_id == cliente.id,
        db.func.date(Asistencia.fecha) == hoy_iso
    ).first()

    if existente:
        flash("Ya registraste tu asistencia para hoy.", "warning")
        return redirect(url_for("cliente.detalles_cliente", id=cliente.id))

    # Guardar asistencia (usar UTC)
    nueva = Asistencia(cliente_id=cliente.id, fecha=datetime.utcnow())
    db.session.add(nueva)
    try:
        db.session.commit()
        flash("Asistencia registrada correctamente.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error al registrar la asistencia: {str(e)}", "danger")
    return redirect(url_for("cliente.detalles_cliente", id=cliente.id))

# ---------------------------------
# Borrar asistencia (admin)
# ---------------------------------

@asistencia_bp.route("/eliminar/<int:id>", methods=["POST"])
@login_required
@roles_required("ADMIN")
def eliminar_asistencia(id):
    asistencia = Asistencia.query.get_or_404(id)
    try:
        db.session.delete(asistencia)
        db.session.commit()
        flash("Asistencia eliminada correctamente.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"No se pudo eliminar la asistencia: {str(e)}", "danger")
    return redirect(url_for("asistencia.lista_asistencias"))
