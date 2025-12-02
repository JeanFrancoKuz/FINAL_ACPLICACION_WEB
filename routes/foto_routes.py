import os
from datetime import datetime, timezone
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, abort, current_app
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from extensions import db
from models.fotos import Foto
from routes.decoradores import roles_required


# ================================================================
# CONFIGURACIÓN
# ================================================================
ALLOWED_ENTITIES = {"CLIENTE"}                          # ← Puedes agregar luego PAGO / PROGRESO
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "mp4"}

foto_bp = Blueprint("foto", __name__, url_prefix="/fotos")


def allowed_file(filename: str) -> bool:
    """Extensiones permitidas."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ================================================================
# 📤 SUBIR FOTO — (cliente o admin)
# ================================================================
@foto_bp.route("/subir/<string:entidad>/<int:entidad_id>", methods=["GET", "POST"])
@login_required
def subir_foto(entidad, entidad_id):

    entidad_upper = entidad.upper()

    # Validar entidad existe
    if entidad_upper not in ALLOWED_ENTITIES:
        flash("Entidad no válida para subida de fotos.", "danger")
        return redirect(url_for("index"))

    # CLIENTE solo puede subir a su propio perfil
    if current_user.rol.nombre.upper() == "CLIENTE" and current_user.cliente.id != entidad_id:
        flash("No tienes permiso para subir imágenes a otro usuario.", "danger")
        return redirect(url_for("index"))

    # 📥 POST = Guardar archivo
    if request.method == "POST":
        archivo = request.files.get("foto")

        if not archivo or archivo.filename.strip() == "":
            flash("Debe seleccionar un archivo.", "warning")
            return redirect(request.url)

        original = secure_filename(archivo.filename)

        if not allowed_file(original):
            flash("Formato no permitido. Permitidos: jpg, png, gif, mp4.", "danger")
            return redirect(request.url)

        # Nombre con marca de tiempo única
        ext = original.rsplit(".", 1)[1].lower()
        nombre_archivo = f"{entidad}_{entidad_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.{ext}"

        # Guardado en /static/uploads/
        upload_dir = os.path.join(current_app.root_path, "static", "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        archivo.save(os.path.join(upload_dir, nombre_archivo))

        # ⚡ Registro BD corregido
        foto = Foto(
            nombre_archivo=nombre_archivo,
            ruta=f"uploads/{nombre_archivo}",
            cliente_id=entidad_id,          # 👈 Cliente siempre
            pago_id=None,                   # 👈 FIX
            progreso_id=None,               # 👈 FIX
            uploaded_by=current_user.id
        )

        db.session.add(foto)

        try:
            db.session.commit()
            flash("📸 Imagen subida correctamente.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Error al guardar: {e}", "danger")
            return redirect(request.url)

        # Redirección según tipo de entidad
        if entidad_upper == "CLIENTE":
            return redirect(url_for("cliente.detalles_cliente", id=entidad_id))

        return redirect(url_for("index"))

    return render_template("fotos/subir_foto.html", entidad=entidad, entidad_id=entidad_id)


# ================================================================
# 📷 LISTA GENERAL DE FOTOS (ADMIN)
# ================================================================
@foto_bp.route("/lista")
@login_required
@roles_required("ADMIN")
def lista_fotos():
    fotos = Foto.query.order_by(Foto.fecha_subida.desc()).all()
    return render_template("admin/lista_fotos.html", fotos=fotos)


# ================================================================
# ❌ ELIMINAR FOTO (ADMIN)
# ================================================================
@foto_bp.route("/eliminar/<int:id>", methods=["POST"])
@login_required
@roles_required("ADMIN")
def eliminar_foto(id):
    foto = Foto.query.get_or_404(id)

    try:
        # 1️⃣ borrar archivo físico si existe
        try:
            file_path = os.path.join(current_app.root_path, "static", foto.ruta)
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            print(f"[WARN] archivo físico no encontrado: {foto.ruta}")

        # 2️⃣ eliminar de BD
        db.session.delete(foto)
        db.session.commit()
        flash("Foto eliminada correctamente.", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"No se pudo eliminar la foto: {e}", "danger")

    return redirect(url_for("foto.lista_fotos"))
