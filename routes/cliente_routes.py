import os
from datetime import datetime, date, timedelta, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from extensions import db
from models.clientes import Cliente, EstadoMembresia
from models.fotos import Foto
from models.pagos import Pago, TipoPago, EstadoPago
from routes.decoradores import roles_required


cliente_bp = Blueprint("cliente", __name__, url_prefix="/cliente")


# ---------------------------------------------------------------------------
# 🟩 Helper de ruta de comprobantes
# ---------------------------------------------------------------------------
def get_comprobantes_dir():
    base = os.path.join(current_app.root_path, "static", "uploads", "comprobantes")
    os.makedirs(base, exist_ok=True)
    return base


# ---------------------------------------------------------------------------
# 🟩 Dashboard del cliente
# ---------------------------------------------------------------------------
@cliente_bp.route("/dashboard")
@login_required
@roles_required("CLIENTE")
def dashboard_cliente():
    cliente = current_user.cliente

    asistencias_mes = len([
        a for a in cliente.asistencias
        if a.fecha.month == datetime.now().month and a.fecha.year == datetime.now().year
    ])

    pagos_pendientes = len([p for p in cliente.pagos if p.estado == EstadoPago.PENDIENTE])

    return render_template(
        "cliente/dashboard_cliente.html",
        cliente=cliente,
        asistencias_mes=asistencias_mes,
        pagos_pendientes=pagos_pendientes
    )


# ---------------------------------------------------------------------------
# 🔎 Ver perfil del cliente (admin o dueño)
# ---------------------------------------------------------------------------
@cliente_bp.route("/perfil/<int:id>")
@login_required
def detalles_cliente(id):
    cliente = Cliente.query.get_or_404(id)

    # si es cliente solo puede ver el suyo
    if current_user.rol.nombre.upper() == "CLIENTE" and current_user.cliente.id != id:
        flash("No tienes permiso para ver otro perfil.", "danger")
        return redirect(url_for("cliente.dashboard_cliente"))

    return render_template(
        "cliente/cliente_detalle_cliente.html",
        cliente=cliente,
        fotos=cliente.fotos,
        pagos=cliente.pagos
    )


# ---------------------------------------------------------------------------
# 📥 Subir comprobante de pago
# ---------------------------------------------------------------------------
@cliente_bp.route("/subir_comprobante/<int:id>", methods=["GET", "POST"])
@login_required
def subir_comprobante(id):
    cliente = Cliente.query.get_or_404(id)

    if current_user.rol.nombre.upper() == "CLIENTE" and current_user.cliente.id != id:
        abort(403)

    if request.method == "POST":
        archivo = request.files.get("comprobante")

        if archivo:
            ext = os.path.splitext(archivo.filename)[1].lower()
            if ext not in [".jpg", ".jpeg", ".png", ".pdf"]:
                flash("Formato permitido: JPG, PNG o PDF.", "danger")
                return redirect(request.url)

            nombre_archivo = secure_filename(
                f"comprobante_{cliente.id}_{datetime.utcnow():%Y%m%d%H%M%S}{ext}"
            )

            dir_absoluto = get_comprobantes_dir()
            ruta_absoluta = os.path.join(dir_absoluto, nombre_archivo)
            archivo.save(ruta_absoluta)

            try:
                pago = Pago(
                    cliente_id=cliente.id,
                    monto=0.0,  # se llena luego en admin
                    tipo=TipoPago.TRANSFERENCIA,
                    estado=EstadoPago.PENDIENTE
                )
                db.session.add(pago)
                db.session.flush()

                foto = Foto(
                    nombre_archivo=nombre_archivo,
                    ruta=f"uploads/comprobantes/{nombre_archivo}",
                    pago=pago,
                    uploaded_by=current_user.id
                )
                db.session.add(foto)

                cliente.estado_membresia = EstadoMembresia.PENDIENTE
                db.session.commit()
                flash("Comprobante enviado. Pendiente de revisión.", "success")

            except Exception as e:
                db.session.rollback()
                flash(f"Error → {e}", "danger")

            return redirect(url_for("cliente.detalles_cliente", id=id))

    return render_template("cliente/subir_comprobante.html", cliente=cliente)


# ---------------------------------------------------------------------------
# 📸 Subir foto de perfil
# ---------------------------------------------------------------------------
@cliente_bp.route("/subir_foto_perfil/<int:id>", methods=["GET", "POST"])
@login_required
@roles_required("CLIENTE")
def subir_foto_perfil(id):
    cliente = Cliente.query.get_or_404(id)

    if current_user.cliente.id != id:
        flash("No puedes cambiar la foto a otro cliente.", "danger")
        return redirect(url_for("cliente.dashboard_cliente"))

    if request.method == "POST":
        archivo = request.files.get("foto")

        if archivo:
            ext = os.path.splitext(archivo.filename)[1].lower()
            if ext not in [".jpg", ".jpeg", ".png"]:
                flash("La foto debe ser JPG o PNG.", "warning")
                return redirect(request.url)

            nombre_archivo = secure_filename(
                f"profile_{cliente.id}_{datetime.utcnow():%Y%m%d%H%M%S}{ext}"
            )

            profile_dir = os.path.join(current_app.root_path, "static", "uploads", "perfil")
            os.makedirs(profile_dir, exist_ok=True)
            archivo.save(os.path.join(profile_dir, nombre_archivo))

            cliente.foto_perfil = f"uploads/perfil/{nombre_archivo}"

            try:
                db.session.commit()
                flash("Foto actualizada ✔", "success")
            except Exception as e:
                db.session.rollback()
                flash(f"Error al guardar: {e}", "danger")

            return redirect(url_for("cliente.detalles_cliente", id=id))

    return render_template("cliente/subir_foto_perfil.html", cliente=cliente)
