import os
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from extensions import db
from models.progreso_cliente import ProgresoCliente
from models.fotos import Foto
from routes.decoradores import roles_required

progreso_bp = Blueprint("progreso", __name__, url_prefix="/progreso")

# ---------------------------
# Historial de progreso (solo cliente)
# ---------------------------
@progreso_bp.route("/historial")
@login_required
@roles_required("CLIENTE")
def historial_progreso():
    progresos = ProgresoCliente.query.filter_by(
        cliente_id=current_user.cliente.id
    ).order_by(ProgresoCliente.fecha_registro.desc()).all()

    return render_template("clientes/historial_progreso.html", progresos=progresos)

# ---------------------------
# Registrar nuevo progreso
# ---------------------------
@progreso_bp.route("/registrar", methods=["GET", "POST"])
@login_required
@roles_required("CLIENTE")
def registrar_progreso():
    if request.method == "POST":
        peso = request.form.get("peso")
        altura = request.form.get("altura")
        grasa = request.form.get("grasa_corporal")
        musculo = request.form.get("masa_muscular")

        try:
            nuevo = ProgresoCliente(
                cliente_id=current_user.cliente.id,
                fecha_registro=datetime.now(timezone.utc),
                peso=float(peso),
                altura=float(altura),
                grasa_corporal=float(grasa) if grasa else None,
                masa_muscular=float(musculo) if musculo else None
            )
            db.session.add(nuevo)
            db.session.commit()
            flash("Progreso registrado correctamente.", "success")
        except ValueError as e:
            db.session.rollback()
            flash(str(e), "danger")
        except Exception as e:
            db.session.rollback()
            flash(f"Error al registrar progreso: {str(e)}", "danger")

        return redirect(url_for("progreso.historial_progreso"))

    return render_template("clientes/registrar_progreso.html")

# ---------------------------
# Subir foto de progreso 
# ---------------------------
@progreso_bp.route("/foto/<int:progreso_id>", methods=["GET", "POST"])
@login_required
@roles_required("CLIENTE")
def subir_foto_progreso(progreso_id):
    progreso = ProgresoCliente.query.get_or_404(progreso_id)

    # Validar que el progreso pertenece al cliente actual
    if progreso.cliente_id != current_user.cliente.id:
        flash("No tienes permiso para subir fotos de otro cliente.", "danger")
        return redirect(url_for("index"))

    if request.method == "POST":
        archivo = request.files.get("foto")
        if archivo:
            ext = os.path.splitext(archivo.filename)[1].lower()
            if ext not in [".jpg", ".jpeg", ".png"]:
                flash("Formato de archivo no permitido. Usa JPG o PNG.", "danger")
                return redirect(request.url)

            nombre_archivo = secure_filename(
                f"progreso_{progreso.id}_{datetime.now(timezone.utc).strftime('%Y%m%d')}{ext}"
            )
            progresos_dir = os.path.join(current_app.root_path, "static", "progresos")
            os.makedirs(progresos_dir, exist_ok=True)
            archivo.save(os.path.join(progresos_dir, nombre_archivo))

            ruta_relativa = f"progresos/{nombre_archivo}"

            try:
                foto = Foto(
                    nombre_archivo=nombre_archivo,
                    ruta=ruta_relativa,   # <-- ruta relativa para usar en templates
                    progreso=progreso,
                    uploaded_by=current_user.id
                )
                db.session.add(foto)
                db.session.commit()
                flash("Foto de progreso subida correctamente.", "success")
            except Exception as e:
                db.session.rollback()
                flash(f"Error al subir foto: {str(e)}", "danger")

            return redirect(url_for("progreso.historial_progreso"))

    return render_template("clientes/subir_foto_progreso.html", progreso=progreso)