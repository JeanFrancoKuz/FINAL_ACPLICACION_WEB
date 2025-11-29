import os
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from extensions import db
from models.progreso_cliente import ProgresoCliente
from models.fotos import Foto
from routes.decoradores import roles_required


progreso_bp = Blueprint("progreso", __name__, url_prefix="/progreso")


# =======================================================
# 🟢 Helper único para guardar imágenes
# =======================================================
def get_dir():
    ruta = os.path.join(current_app.root_path, "static", "uploads", "progresos")
    os.makedirs(ruta, exist_ok=True)
    return ruta


# =======================================================
# 📌 HISTORIAL DEL CLIENTE — SOLO CLIENTE
# =======================================================
@progreso_bp.route("/registrar", methods=["GET", "POST"])
@login_required
@roles_required("CLIENTE")
def registrar_progreso():
    cliente = current_user.cliente

    # Obtener total de progresos existentes
    progresos = ProgresoCliente.query.filter_by(cliente_id=cliente.id)\
                                    .order_by(ProgresoCliente.fecha_registro.desc()).all()

    limite = 12

    if request.method == "POST":
        # Si llega a 12, eliminamos el más antiguo antes de registrar el nuevo
        if len(progresos) >= limite:
            progreso_antiguo = progresos[-1]  # último en lista = el más antiguo
            db.session.delete(progreso_antiguo)
            db.session.commit()

            flash(f"⚠ Se alcanzó el límite de 12 progresos. El registro más antiguo fue eliminado automáticamente.", "warning")

        # Registrar nuevo progreso
        try:
            nuevo = ProgresoCliente(
                cliente_id=cliente.id,
                fecha_registro=datetime.now(timezone.utc),
                peso=float(request.form.get("peso")),
                altura=float(request.form.get("altura")),
                grasa_corporal=float(request.form.get("grasa_corporal")) if request.form.get("grasa_corporal") else None,
                masa_muscular=float(request.form.get("masa_muscular")) if request.form.get("masa_muscular") else None,
            )

            db.session.add(nuevo)
            db.session.commit()

            flash("Progreso registrado correctamente ✔", "success")
            return redirect(url_for("progreso.historial_progreso"))

        except Exception as e:
            db.session.rollback()
            flash(f"Error al registrar progreso: {e}", "danger")

    return render_template("cliente/registrar_progreso.html", total=len(progresos), limite=limite)

# =======================================================
# 📸 Subir Foto de Progreso
# =======================================================
@progreso_bp.route("/foto/<int:progreso_id>", methods=["GET", "POST"])
@login_required
@roles_required("CLIENTE")
def subir_foto_progreso(progreso_id):
    progreso = ProgresoCliente.query.get_or_404(progreso_id)

    if progreso.cliente_id != current_user.cliente.id:
        abort(403)

    if request.method == "POST":
        archivo = request.files.get("foto")

        if archivo:
            ext = os.path.splitext(archivo.filename)[1].lower()
            if ext not in [".jpg", ".jpeg", ".png"]:
                flash("Formato no permitido. Usa JPG o PNG.", "danger")
                return redirect(request.url)

            filename = secure_filename(f"progreso_{progreso.id}_{datetime.utcnow():%Y%m%d%H%M%S}{ext}")
            archivo.save(os.path.join(get_dir(), filename))

            try:
                foto = Foto(
                    nombre_archivo=filename,
                    ruta=f"uploads/progresos/{filename}",
                    progreso=progreso,
                    uploaded_by=current_user.id
                )
                db.session.add(foto)
                db.session.commit()
                flash("Foto subida correctamente.", "success")

            except Exception as e:
                db.session.rollback()
                flash(f"Error al subir foto: {e}", "danger")

        return redirect(url_for("progreso.historial_progreso"))

    return render_template("cliente/subir_foto_progreso.html", progreso=progreso)


# =======================================================
# Historial
# =======================================================
@progreso_bp.route("/historial")
@login_required
@roles_required("CLIENTE")
def historial_progreso():

    # Obtener los progresos por fecha (descendente)
    progresos = ProgresoCliente.query.filter_by(
        cliente_id=current_user.cliente.id
    ).order_by(ProgresoCliente.fecha_registro.desc()).all()

    total = len(progresos)

    # Si existen más de 12 → mantener solo los 12 más recientes
    if total > 12:
        eliminar = progresos[12:]  # Todo lo que esté después del top 12

        for p in eliminar:
            db.session.delete(p)

        db.session.commit()
        flash("📌 Se alcanzó el máximo (12 progresos). Se eliminaron los más antiguos automáticamente.", "warning")

    # Volver a consultar para mostrar solo los válidos
    progresos = ProgresoCliente.query.filter_by(
        cliente_id=current_user.cliente.id
    ).order_by(ProgresoCliente.fecha_registro.desc()).limit(12).all()

    return render_template("cliente/historial_progreso.html", progresos=progresos)

# =======================================================
# Comparacion
# =======================================================

@progreso_bp.route("/comparacion")
@login_required
@roles_required("CLIENTE")
def comparar_progreso():
    progresos = ProgresoCliente.query.filter_by(cliente_id=current_user.cliente.id)\
                                    .order_by(ProgresoCliente.fecha_registro.asc()).all()

    if len(progresos) < 2:
        flash("Debes tener al menos 2 progresos para comparar", "warning")
        return redirect(url_for("progreso.historial_progreso"))

    return render_template(
        "cliente/comparacion_progreso.html",
        progreso_inicial=progresos[0],
        progreso_reciente=progresos[-1]
    )
