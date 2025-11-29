from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from extensions import db
from models.asistencias import Asistencia
from models.clientes import Cliente
from routes.decoradores import roles_required


asistencia_bp = Blueprint("asistencia", __name__, url_prefix="/asistencias")


# ======================================================
# 🔹 1) LISTA GENERAL (SOLO ADMIN)
# ======================================================
@asistencia_bp.route("/lista")
@login_required
@roles_required("ADMIN")
def lista_asistencias():
    page = request.args.get("page", 1, type=int)
    asistencias = Asistencia.query.order_by(
        Asistencia.fecha.desc()
    ).paginate(page=page, per_page=20, error_out=False)

    return render_template("admin/lista_asistencias.html", asistencias=asistencias)


# ======================================================
# 🔹 2) Registrar asistencia — Cliente
# ======================================================
@asistencia_bp.route("/registrar", methods=["POST"])
@login_required
def registrar_asistencia():
    if not current_user.cliente:
        flash("Tu cuenta no está asociada a un perfil de cliente.", "danger")
        return redirect(url_for("index"))

    cliente = current_user.cliente

    # Evitar duplicado por fecha (conversión correcta a DATE ISO)
    hoy = datetime.now(timezone.utc).date()

    existente = (
        Asistencia.query.filter(Asistencia.cliente_id == cliente.id)
        .filter(db.func.date(Asistencia.fecha) == hoy)
        .first()
    )

    if existente:
        flash("Ya registraste tu asistencia hoy.", "warning")
        return redirect(url_for("cliente.detalles_cliente", id=cliente.id))

    nueva = Asistencia(cliente_id=cliente.id, fecha=datetime.now(timezone.utc))

    db.session.add(nueva)
    try:
        db.session.commit()
        flash("Asistencia registrada correctamente.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error al guardar asistencia: {e}", "danger")

    return redirect(url_for("cliente.detalles_cliente", id=cliente.id))


# ======================================================
# 🔹 3) Historial del cliente (solo cliente)
# ======================================================
@asistencia_bp.route("/historial")
@login_required
@roles_required("CLIENTE")
def historial_asistencias_cliente():
    asistencias = (
        Asistencia.query.filter_by(cliente_id=current_user.cliente.id)
        .order_by(Asistencia.fecha.desc())
        .all()
    )

    return render_template("cliente/historial_asistencias.html", asistencias=asistencias)


# ======================================================
# 🔹 4) Historial admin por cliente
# ======================================================
@asistencia_bp.route("/cliente/<int:id>")
@login_required
@roles_required("ADMIN")
def historial_cliente_admin(id):
    cliente = Cliente.query.get_or_404(id)
    asistencias = Asistencia.query.filter_by(cliente_id=id).order_by(Asistencia.fecha.desc()).all()

    return render_template("admin/historial_asistencias_cliente.html", cliente=cliente, asistencias=asistencias)


# ======================================================
# 🔹 5) Eliminar asistencia — ADMIN
# ======================================================
@asistencia_bp.route("/eliminar/<int:id>", methods=["POST"])
@login_required
@roles_required("ADMIN")
def eliminar_asistencia(id):
    asistencia = Asistencia.query.get_or_404(id)
    try:
        db.session.delete(asistencia)
        db.session.commit()
        flash("Asistencia eliminada.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"No se pudo eliminar: {e}", "danger")

    return redirect(url_for("asistencia.lista_asistencias"))
