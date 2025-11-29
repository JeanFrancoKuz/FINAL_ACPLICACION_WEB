import os
from datetime import datetime, date, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from extensions import db
from models.clientes import Cliente, EstadoMembresia
from models.fotos import Foto
from models.pagos import Pago, TipoPago, EstadoPago
from models.usuarios import Usuario   # IMPORT NECESARIO PARA password update
from routes.decoradores import roles_required


cliente_bp = Blueprint("cliente", __name__, url_prefix="/cliente")


# ===============================================================
# 📁 Carpeta estándar para archivos & fotos
# ===============================================================
def get_dir():
    ruta = os.path.join(current_app.root_path, "static", "uploads", "comprobantes")
    os.makedirs(ruta, exist_ok=True)
    return ruta



# ===============================================================
# 🏠  DASHBOARD CLIENTE
# ===============================================================
@cliente_bp.route("/dashboard")
@login_required
@roles_required("CLIENTE")
def dashboard_cliente():
    cliente = current_user.cliente
    hoy = date.today()

    asistencias_mes = len([
        a for a in cliente.asistencias
        if a.fecha.month == hoy.month and a.fecha.year == hoy.year
    ])

    pagos_pendientes = len([p for p in cliente.pagos if p.estado == EstadoPago.PENDIENTE])

    return render_template(
        "cliente/dashboard_cliente.html",
        cliente=cliente,
        asistencias_mes=asistencias_mes,
        pagos_pendientes=pagos_pendientes
    )



# ===============================================================
# 👤 PERFIL CLIENTE — SE ENVÍA "today" PARA JINJA
# ===============================================================
@cliente_bp.route("/perfil/<int:id>")
@login_required
def detalles_cliente(id):
    cliente = Cliente.query.get_or_404(id)

    # Un cliente solo puede ver su propio perfil
    if current_user.rol.nombre.upper() == "CLIENTE" and current_user.cliente.id != id:
        flash("No puedes ver otro perfil ❌", "danger")
        return redirect(url_for("cliente.dashboard_cliente"))

    today = date.today()

    return render_template(
        "cliente/perfil_cliente.html",
        cliente=cliente,
        today=today
    )



# ===============================================================
# ✏ EDITAR PERFIL DEL CLIENTE
# ===============================================================
@cliente_bp.route("/perfil/editar/<int:id>", methods=["GET","POST"])
@login_required
@roles_required("CLIENTE")
def editar_perfil_cliente(id):
    cliente = Cliente.query.get_or_404(id)

    if current_user.cliente.id != id:
        flash("No puedes modificar otro perfil ❌", "danger")
        return redirect(url_for("cliente.dashboard_cliente"))

    if request.method == "POST":
        cliente.nombre   = request.form.get("nombre")
        cliente.correo   = request.form.get("correo") or None
        cliente.telefono = request.form.get("telefono") or None

        # Cambiar contraseña opcionalmente
        nueva_clave = request.form.get("password")
        if nueva_clave:
            cliente.usuario.set_password(nueva_clave)

        db.session.commit()
        flash("Perfil actualizado con éxito ✔", "success")
        return redirect(url_for("cliente.detalles_cliente", id=id))

    return render_template("cliente/editar_perfil_cliente.html", cliente=cliente)



# ===============================================================
# 📤 SUBIR COMPROBANTE DE PAGO
# ===============================================================
@cliente_bp.route("/subir_comprobante/<int:id>", methods=["GET","POST"])
@login_required
def subir_comprobante(id):
    cliente = Cliente.query.get_or_404(id)

    if current_user.rol.nombre.upper() == "CLIENTE" and current_user.cliente.id != id:
        abort(403)

    if request.method == "POST":
        archivo = request.files.get("comprobante")

        if archivo:
            ext = os.path.splitext(archivo.filename)[1].lower()
            if ext not in [".jpg",".jpeg",".png",".pdf"]:
                flash("Solo JPG / PNG / PDF", "danger")
                return redirect(request.url)

            filename = secure_filename(f"comprobante_{id}_{datetime.utcnow():%Y%m%d%H%M%S}{ext}")
            archivo.save(os.path.join(get_dir(), filename))

            pago = Pago(cliente_id=id,monto=0.0,tipo=TipoPago.TRANSFERENCIA,estado=EstadoPago.PENDIENTE)
            db.session.add(pago); db.session.flush()

            db.session.add(Foto(
                nombre_archivo=filename,
                ruta=f"uploads/comprobantes/{filename}",
                pago=pago,
                uploaded_by=current_user.id
            ))

            cliente.estado_membresia = EstadoMembresia.PENDIENTE
            db.session.commit()
            flash("Comprobante enviado 🔄 en revisión", "success")

            return redirect(url_for("cliente.detalles_cliente", id=id))

    return render_template("cliente/subir_comprobante.html", cliente=cliente)



# ===============================================================
# 🖼 SUBIR FOTO DE PERFIL
# ===============================================================
@cliente_bp.route("/subir_foto_perfil/<int:id>", methods=["GET","POST"])
@login_required
@roles_required("CLIENTE")
def subir_foto_perfil(id):
    cliente = Cliente.query.get_or_404(id)

    if current_user.cliente.id != id:
        flash("No puedes modificar otro perfil ❌", "danger")
        return redirect(url_for("cliente.dashboard_cliente"))

    if request.method == "POST":
        archivo = request.files.get("foto")

        if archivo:
            ext = os.path.splitext(archivo.filename)[1].lower()
            if ext not in [".jpg",".jpeg",".png"]:
                flash("Formato inválido ❗", "warning")
                return redirect(request.url)

            perfil_dir = os.path.join(current_app.root_path,"static","uploads","perfil")
            os.makedirs(perfil_dir, exist_ok=True)

            filename = secure_filename(f"profile_{id}_{datetime.utcnow():%Y%m%d%H%M%S}{ext}")
            archivo.save(os.path.join(perfil_dir, filename))

            cliente.foto_perfil = f"uploads/perfil/{filename}"
            db.session.commit()
            flash("Foto actualizada ✔", "success")

        return redirect(url_for("cliente.detalles_cliente", id=id))

    return render_template("cliente/subir_foto_perfil.html", cliente=cliente)



# ===============================================================
# 💳 REGISTRAR PAGO — CLIENTE
# ===============================================================
@cliente_bp.route("/pagos/registrar", methods=["GET","POST"])
@login_required
@roles_required("CLIENTE")
def registrar_pago_cliente():
    cliente = current_user.cliente

    if request.method == "POST":
        monto = request.form.get("monto")
        tipo  = request.form.get("tipo")
        archivo = request.files.get("comprobante")

        if not monto or not tipo:
            flash("Monto y tipo son obligatorios ❗", "danger")
            return redirect(request.url)

        try:
            pago = Pago(
                cliente_id=cliente.id, monto=float(monto),
                tipo=TipoPago[tipo.upper()], estado=EstadoPago.PENDIENTE,
                fecha_pago=datetime.now(timezone.utc)
            )
            db.session.add(pago); db.session.flush()

            if archivo and archivo.filename:
                ext = os.path.splitext(archivo.filename)[1].lower()
                if ext not in [".jpg",".jpeg",".png",".pdf"]:
                    flash("Archivo inválido", "danger"); return redirect(request.url)

                filename = secure_filename(f"pago_{pago.id}_{datetime.utcnow():%Y%m%d%H%M%S}{ext}")
                archivo.save(os.path.join(get_dir(), filename))

                db.session.add(Foto(
                    nombre_archivo=filename,
                    ruta=f"uploads/comprobantes/{filename}",
                    pago=pago,
                    uploaded_by=current_user.id
                ))

            db.session.commit()
            flash("Pago enviado 🟡 Pendiente de validación", "success")

        except Exception as e:
            db.session.rollback()
            flash(f"Error al registrar pago: {e}", "danger")

        return redirect(url_for("cliente.dashboard_cliente"))

    return render_template("cliente/registrar_pago_cliente.html")
