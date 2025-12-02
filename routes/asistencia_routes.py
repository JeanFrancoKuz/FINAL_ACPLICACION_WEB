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
    fecha_str = request.args.get("fecha", "")

    query = Asistencia.query.join(Cliente).order_by(Asistencia.fecha.desc())

    # 🔍 Filtro por fecha exacta
    if fecha_str:
        try:
            fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            query = query.filter(db.func.date(Asistencia.fecha) == fecha)
        except ValueError:
            flash("Formato de fecha inválido.", "warning")

    asistencias = query.paginate(page=page, per_page=15)

    return render_template(
        "admin/lista_asistencias.html",
        asistencias=asistencias
    )

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

    hoy = datetime.now(timezone.utc).date()

    existente = (
        Asistencia.query.filter(Asistencia.cliente_id == cliente.id)
        .filter(db.func.date(Asistencia.fecha) == hoy)
        .first()
    )

    if existente:
        flash("Ya registraste tu asistencia hoy.", "warning")
        return redirect(url_for("asistencia.historial_asistencias_cliente"))

    nueva = Asistencia(cliente_id=cliente.id, fecha=datetime.now(timezone.utc))

    db.session.add(nueva)
    try:
        db.session.commit()
        flash("Asistencia registrada correctamente.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error al guardar asistencia: {e}", "danger")

    return redirect(url_for("asistencia.historial_asistencias_cliente"))



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

    # Convertimos asistencias → FullCalendar JSON
    asistencias_json = [
        {
            "title": "Asistencia",
            "start": a.fecha.date().isoformat(),   # YYYY-MM-DD
        }
        for a in asistencias
    ]

    # 🔥 NUEVO: fecha de ingreso
    fecha_ingreso = current_user.cliente.fecha_ingreso.isoformat()

    return render_template(
        "cliente/historial_asistencias.html",
        asistencias_json=asistencias_json,
        fecha_ingreso=fecha_ingreso,   # 👈 NUEVO
    )

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

@asistencia_bp.route("/historial/json")
@login_required
@roles_required("CLIENTE")
def historial_asistencias_json():
    asistencias = (
        Asistencia.query
        .filter_by(cliente_id=current_user.cliente.id)
        .order_by(Asistencia.fecha.asc())
        .all()
    )

    eventos = []
    for a in asistencias:
        eventos.append({
            "title": "✔ Asistencia",
            "start": a.fecha.strftime("%Y-%m-%d")
        })

    return eventos
