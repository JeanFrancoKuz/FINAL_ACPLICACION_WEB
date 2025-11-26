import os
from datetime import datetime, timezone

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from extensions import db
from models.fotos import Foto
from routes.decoradores import roles_required  

# ----------------------------------------------
# 1️ Parámetros de configuración
# ----------------------------------------------
ALLOWED_ENTITIES = {"CLIENTE"}  
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "mp4"}

def allowed_file(filename: str) -> bool:
    """Filtra los tipos de archivo permitidos."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


foto_bp = Blueprint("foto", __name__, url_prefix="/fotos")

# ----------------------------------------------
# Subir foto asociada a una entidad
# ----------------------------------------------
@foto_bp.route("/subir/<string:entidad>/<int:entidad_id>", methods=["GET", "POST"])
@login_required
def subir_foto(entidad, entidad_id):
    entidad_upper = entidad.upper()
    if entidad_upper not in ALLOWED_ENTITIES:
        flash(f"Entidad '{entidad}' no permitida.", "danger")
        return redirect(url_for("index"))

    # --- Permiso de acceso ---
    if current_user.rol.nombre.upper() == "CLIENTE":
        if current_user.cliente.id != entidad_id:
            flash("No tienes permiso para subir fotos a este cliente.", "danger")
            return redirect(url_for("index"))

    if request.method == "POST":
        archivo = request.files.get("foto")
        if not archivo:
            flash("Selecciona un archivo antes de enviar.", "warning")
            return redirect(request.url)

        original_name = secure_filename(archivo.filename)
        if not allowed_file(original_name):
            flash("Archivo no permitido. Usa JPG, PNG, GIF o MP4.", "danger")
            return redirect(request.url)

        ext = original_name.rsplit(".", 1)[1].lower()
        nombre_archivo = f"{entidad}_{entidad_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.{ext}"
        ruta_relativa = f"uploads/{nombre_archivo}"
        ruta_absoluta = os.path.join(current_app.root_path, "static", "uploads")
        os.makedirs(ruta_absoluta, exist_ok=True)
        archivo.save(os.path.join(ruta_absoluta, nombre_archivo))

        foto = Foto(
            nombre_archivo=nombre_archivo,
            ruta=ruta_relativa,
            uploaded_by=current_user.id,
        )

        if entidad_upper == "CLIENTE":
            foto.cliente_id = entidad_id

        db.session.add(foto)
        try:
            db.session.commit()
            flash("Foto subida correctamente.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Error al guardar la foto: {str(e)}", "danger")
            return redirect(request.url)

        if entidad_upper == "CLIENTE":
            return redirect(url_for("cliente.detalles_cliente", id=entidad_id))

        return redirect(url_for("index"))

    return render_template("fotos/subir_foto.html", entidad=entidad, entidad_id=entidad_id)

# ----------------------------------------------
# Lista de fotos (solo admin)
# ----------------------------------------------
@foto_bp.route("/lista")
@login_required
@roles_required("ADMIN")  
def lista_fotos():
    fotos = Foto.query.order_by(Foto.fecha_subida.desc()).all()
    return render_template("admin/lista_fotos.html", fotos=fotos)

# ----------------------------------------------
#Eliminar foto (solo admin)
# ----------------------------------------------
@foto_bp.route("/eliminar/<int:id>", methods=["POST"])
@login_required
@roles_required("ADMIN")
def eliminar_foto(id):
    foto = Foto.query.get_or_404(id)
    try:
        # eliminar archivo físico (si existe)
        try:
            ruta_rel = foto.ruta  # ej. "uploads/xxx.jpg" o "comprobantes/xxx.pdf"
            ruta_abs = os.path.join(current_app.root_path, "static", ruta_rel)
            if os.path.exists(ruta_abs):
                os.remove(ruta_abs)
        except Exception:
            # no interrumpir borrado en BD si falla el FS; simplemente loguear en consola
            print(f"[WARN] No se pudo eliminar archivo fisico {getattr(foto, 'ruta', None)}")

        db.session.delete(foto)
        db.session.commit()
        flash("Foto eliminada correctamente.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error al eliminar la foto: {str(e)}", "danger")
    return redirect(url_for("foto.lista_fotos"))