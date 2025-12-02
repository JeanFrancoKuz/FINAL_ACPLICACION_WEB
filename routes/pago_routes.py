import os
from datetime import datetime, date
from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash, abort, current_app
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from dateutil.relativedelta import relativedelta

from extensions import db
from models.pagos import Pago, EstadoPago, TipoPago
from models.clientes import Cliente, EstadoMembresia
from models.fotos import Foto
from routes.decoradores import roles_required


pago_bp = Blueprint("pago", __name__, url_prefix="/pagos")


# =====================================================================
# 📁 Carpeta de comprobantes
# =====================================================================
def get_dir():
    ruta = os.path.join(current_app.root_path, "static", "uploads", "comprobantes")
    os.makedirs(ruta, exist_ok=True)
    return ruta


# =====================================================================
# ███ ADMIN — TODAS LAS FUNCIONES Y CRUD COMPLETO
# =====================================================================

# ---------------------------------------------------------
# 📋 LISTA DE PAGOS (ADMIN)
# ---------------------------------------------------------
@pago_bp.route("/lista")
@login_required
@roles_required("ADMIN")
def lista_pagos():
    estado = request.args.get("estado", "")
    q = request.args.get("q", "").strip()

    query = Pago.query.join(Cliente)

    if estado:
        try:
            query = query.filter(Pago.estado == EstadoPago[estado.upper()])
        except KeyError:
            flash("Estado inválido.", "warning")

    if q:
        query = query.filter(
            Cliente.nombre.ilike(f"%{q}%") |
            Cliente.cedula.ilike(f"%{q}%")
        )

    pagos = query.order_by(Pago.fecha_pago.desc()).all()
    return render_template("admin/lista_pagos_admin.html", pagos=pagos)


# ---------------------------------------------------------
# ➕ REGISTRAR PAGO (ADMIN)
# ---------------------------------------------------------
@pago_bp.route("/registrar_admin/<int:cliente_id>", methods=["GET", "POST"])
@login_required
@roles_required("ADMIN")
def registrar_pago_admin(cliente_id):

    # Seleccionar cliente antes
    if cliente_id == 0:
        q = request.args.get("q", "")
        clientes = Cliente.query.filter(
            Cliente.nombre.ilike(f"%{q}%") | Cliente.cedula.ilike(f"%{q}%")
        ).all() if q else Cliente.query.order_by(Cliente.nombre).all()

        return render_template("admin/seleccionar_cliente_pago.html", clientes=clientes)

    cliente = Cliente.query.get_or_404(cliente_id)

    if request.method == "POST":

        monto = request.form.get("monto")
        tipo = request.form.get("tipo")
        archivo = request.files.get("comprobante")

        if not monto or not tipo:
            flash("Monto y tipo requeridos.", "danger")
            return redirect(request.url)

        try:
            # Crear pago
            pago = Pago(
                cliente_id=cliente.id,
                monto=float(monto),
                tipo=TipoPago[tipo.upper()],
                estado=EstadoPago.PENDIENTE,
                fecha_pago=datetime.utcnow()
            )
            db.session.add(pago)
            db.session.flush()

            # Subida de comprobante
            if archivo and archivo.filename:

                ext = os.path.splitext(archivo.filename)[1].lower()
                if ext not in [".jpg", ".jpeg", ".png", ".pdf"]:
                    flash("Formato inválido.", "danger")
                    return redirect(request.url)

                filename = secure_filename(
                    f"pago_{pago.id}_{datetime.utcnow():%Y%m%d%H%M%S}{ext}"
                )

                archivo.save(os.path.join(get_dir(), filename))

                db.session.add(Foto(
                    nombre_archivo=filename,
                    ruta=f"uploads/comprobantes/{filename}",
                    pago=pago,
                    uploaded_by=current_user.id
                ))

            db.session.commit()
            flash("Pago registrado ✔", "success")

        except Exception as e:
            db.session.rollback()
            flash(f"Error: {e}", "danger")

        return redirect(url_for("pago.lista_pagos"))

    return render_template("admin/registrar_pago_admin.html", cliente=cliente)


# ---------------------------------------------------------
# 🟢 VALIDAR / RECHAZAR - (ADMIN)
# ---------------------------------------------------------
@pago_bp.route("/validar/<int:pago_id>", methods=["POST"])
@login_required
@roles_required("ADMIN")
def validar_pago(pago_id):
    pago = Pago.query.get_or_404(pago_id)
    cliente = pago.cliente
    accion = request.form.get("accion")
    hoy = date.today()

    try:
        if accion == "aprobar":
            pago.validar()

            venc = cliente.membresia_vencimiento
            if isinstance(venc, datetime):
                venc = venc.date()

            if venc and venc >= hoy:
                cliente.membresia_vencimiento = venc + relativedelta(months=1)
            else:
                cliente.membresia_vencimiento = hoy + relativedelta(months=1)

            cliente.estado_membresia = EstadoMembresia.ACTIVO

        elif accion == "rechazar":
            pago.rechazar()

        else:
            flash("Acción inválida.", "danger")

        db.session.commit()
        flash("Pago procesado ✔", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Error: {e}", "danger")

    return redirect(url_for("pago.lista_pagos"))


# ---------------------------------------------------------
# ✏ EDITAR PAGO (ADMIN)
# ---------------------------------------------------------
@pago_bp.route("/editar_admin/<int:pago_id>", methods=["GET", "POST"])
@login_required
@roles_required("ADMIN")
def editar_pago_admin(pago_id):
    pago = Pago.query.get_or_404(pago_id)

    if request.method == "POST":
        monto = request.form.get("monto")
        tipo = request.form.get("tipo")
        archivo = request.files.get("comprobante")

        if not monto or not tipo:
            flash("Monto y tipo requeridos.", "danger")
            return redirect(request.url)

        try:
            pago.monto = float(monto)
            pago.tipo  = TipoPago[tipo.upper()]

            if archivo and archivo.filename:
                ext = os.path.splitext(archivo.filename)[1].lower()
                if ext not in [".jpg", ".jpeg", ".png", ".pdf"]:
                    flash("Formato inválido.", "danger")
                    return redirect(request.url)

                filename = secure_filename(
                    f"pago_{pago.id}_{datetime.utcnow():%Y%m%d%H%M%S}{ext}"
                )
                archivo.save(os.path.join(get_dir(), filename))

                db.session.add(Foto(
                    nombre_archivo=filename,
                    ruta=f"uploads/comprobantes/{filename}",
                    pago=pago,
                    uploaded_by=current_user.id
                ))

            db.session.commit()
            flash("Pago actualizado ✔", "success")

        except Exception as e:
            db.session.rollback()
            flash(f"Error: {e}", "danger")

        return redirect(url_for("pago.lista_pagos"))

    return render_template("admin/editar_pago_admin.html", pago=pago)


# ---------------------------------------------------------
# 🗑 ELIMINAR PAGO (ADMIN)
# ---------------------------------------------------------
@pago_bp.route("/eliminar_admin/<int:pago_id>", methods=["POST"])
@login_required
@roles_required("ADMIN")
def eliminar_pago_admin(pago_id):
    pago = Pago.query.get_or_404(pago_id)

    try:
        db.session.delete(pago)
        db.session.commit()
        flash("Pago eliminado ✔", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Error: {e}", "danger")

    return redirect(url_for("pago.lista_pagos"))


# =====================================================================
# ███ CLIENTE — NUEVA ESTRUCTURA
# =====================================================================

# ---------------------------------------------------------
# 🟦 HOME PAGOS CLIENTE (BCV + PLANES + HISTORIAL reducido)
# ---------------------------------------------------------
@pago_bp.route("/cliente")
@login_required
@roles_required("CLIENTE")
def pagos_cliente():
    cliente = current_user.cliente
    pagos = Pago.query.filter_by(cliente_id=cliente.id).order_by(Pago.fecha_pago.desc()).all()

    return render_template(
        "cliente/pagos_cliente.html",
        cliente=cliente,
        pagos=pagos
    )


# ---------------------------------------------------------
# 🟩 REGISTRAR PAGO CLIENTE (PLANES)
# ---------------------------------------------------------
@pago_bp.route("/cliente/registrar", methods=["GET", "POST"])
@login_required
@roles_required("CLIENTE")
def registrar_pago_cliente():
    cliente = current_user.cliente

    if request.method == "POST":

        monto = request.form.get("monto")
        tipo  = request.form.get("tipo")
        archivo = request.files.get("comprobante")

        if not monto or not tipo:
            flash("Monto y tipo requeridos.", "danger")
            return redirect(request.url)

        try:
            pago = Pago(
                cliente_id=cliente.id,
                monto=float(monto),
                tipo=TipoPago[tipo.upper()],
                estado=EstadoPago.PENDIENTE,
                fecha_pago=datetime.utcnow()
            )
            db.session.add(pago)
            db.session.flush()

            if archivo and archivo.filename:

                ext = os.path.splitext(archivo.filename)[1].lower()
                filename = secure_filename(
                    f"pago_{pago.id}_{datetime.utcnow():%Y%m%d%H%M%S}{ext}"
                )
                archivo.save(os.path.join(get_dir(), filename))

                db.session.add(Foto(
                    nombre_archivo=filename,
                    ruta=f"uploads/comprobantes/{filename}",
                    pago=pago,
                    uploaded_by=current_user.id
                ))

            db.session.commit()
            flash("Pago enviado ✔ Pendiente de validación", "success")

        except Exception as e:
            db.session.rollback()
            flash(f"Error: {e}", "danger")

        return redirect(url_for("pago.historial_pagos_cliente"))

    monto_sugerido = request.args.get("monto", type=float)

    return render_template(
        "cliente/registrar_pago_cliente.html",
        cliente=cliente,
        monto_sugerido=monto_sugerido
    )


# ---------------------------------------------------------
# 🟨 HISTORIAL COMPLETO CLIENTE
# ---------------------------------------------------------
@pago_bp.route("/cliente/historial")
@login_required
@roles_required("CLIENTE")
def historial_pagos_cliente():
    cliente = current_user.cliente

    pagos = Pago.query.filter_by(cliente_id=cliente.id).order_by(Pago.fecha_pago.desc()).all()

    return render_template(
        "cliente/historial_pagos_cliente.html",
        cliente=cliente,
        pagos=pagos
    )

# =====================================================
# 🟢 REGISTRAR PAGO (CLIENTE - desde plan con API BCV)
# =====================================================
@pago_bp.route("/registrar", methods=["GET", "POST"])
@login_required
def registrar_pago_cliente_auto():

    bs = request.args.get("bs", type=float)

    if request.method == "POST":

        tipo = request.form.get("tipo")
        archivo = request.files.get("comprobante")
        monto = request.form.get("monto")  # será Bs

        if not monto or not tipo:
            flash("Debe ingresar monto y tipo de pago.", "danger")
            return redirect(request.url)

        try:
            pago = Pago(
                cliente_id=current_user.cliente.id,
                monto=float(monto),  # <- GUARDAMOS SIEMPRE EN BS
                tipo=TipoPago[tipo.upper()],
                estado=EstadoPago.PENDIENTE,
                fecha_pago=datetime.utcnow()
            )
            db.session.add(pago)
            db.session.flush()

            if archivo and archivo.filename:
                ext = os.path.splitext(archivo.filename)[1].lower()
                filename = secure_filename(
                    f"pago_{pago.id}_{datetime.utcnow():%Y%m%d%H%M%S}{ext}"
                )
                archivo.save(os.path.join(get_dir(), filename))

                db.session.add(Foto(
                    nombre_archivo=filename,
                    ruta=f"uploads/comprobantes/{filename}",
                    pago=pago,
                    uploaded_by=current_user.id
                ))

            db.session.commit()
            flash("Pago enviado ✔", "success")

        except Exception as e:
            db.session.rollback()
            flash(f"Error: {e}", "danger")

        return redirect(url_for("pago.historial_pagos_cliente"))

    return render_template(
        "cliente/registrar_pago_cliente.html",
        monto_sugerido=bs   # <- pre-llenamos campo en Bs
    )
