import os
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from dateutil.relativedelta import relativedelta
from sqlalchemy import or_
from extensions import db

from models.pagos import Pago, EstadoPago, TipoPago
from models.clientes import Cliente, EstadoMembresia
from models.fotos import Foto
from routes.decoradores import roles_required

pago_bp = Blueprint("pago", __name__, url_prefix="/pagos")


# ===========================================================
#     📁  Ruta estándar para guardar comprobantes
# ===========================================================
def get_dir():
    ruta = os.path.join(current_app.root_path, "static", "uploads", "comprobantes")
    os.makedirs(ruta, exist_ok=True)
    return ruta


# ===========================================================
#     📌 LISTA DE PAGOS - ADMIN PANEL
# ===========================================================
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
            flash("Estado inválido", "warning")

    if q:
        query = query.filter(
            (Cliente.nombre.ilike(f"%{q}%")) |
            (Cliente.cedula.ilike(f"%{q}%"))
        )

    pagos = query.order_by(Pago.fecha_pago.desc()).all()
    return render_template("admin/lista_pagos_admin.html", pagos=pagos)


# ===========================================================
#     🔵 REGISTRAR PAGO COMO CLIENTE
# ===========================================================
@pago_bp.route("/registrar/<int:cliente_id>", methods=["GET", "POST"])
@login_required
def registrar_pago(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)

    if current_user.rol.nombre.upper() == "CLIENTE" and current_user.cliente.id != cliente_id:
        abort(403)

    if request.method == "POST":
        monto = request.form.get("monto")
        tipo = request.form.get("tipo")

        if not monto or not tipo:
            flash("Monto y tipo de pago son obligatorios.", "danger")
            return redirect(request.url)

        try:
            pago = Pago(
                cliente_id=cliente.id,
                monto=float(monto),
                tipo=TipoPago[tipo.upper()],
                estado=EstadoPago.PENDIENTE,
                fecha_pago=datetime.now(timezone.utc)
            )

            db.session.add(pago)
            db.session.commit()
            flash("Pago registrado. Pendiente de revisión.", "success")

        except Exception as e:
            db.session.rollback()
            flash(f"Error: {e}", "danger")

        return redirect(url_for("cliente.detalles_cliente", id=cliente.id))

    return render_template("cliente/registrar_pago.html", cliente=cliente)


# ===========================================================
#     🟪 REGISTRO DIRECTO DE ADMIN
# ===========================================================
@pago_bp.route("/registrar_admin/<int:cliente_id>", methods=["GET", "POST"])
@login_required
@roles_required("ADMIN")
def registrar_pago_admin(cliente_id):

    # Si cliente_id = 0 → pantalla de selección
    if cliente_id == 0:
        q = request.args.get("q", "").strip()
        clientes = Cliente.query.filter(
            Cliente.nombre.ilike(f"%{q}%") |
            Cliente.cedula.ilike(f"%{q}%")
        ).all() if q else Cliente.query.order_by(Cliente.nombre).all()

        return render_template("admin/seleccionar_cliente_pago.html", clientes=clientes)

    cliente = Cliente.query.get_or_404(cliente_id)

    if request.method == "POST":
        monto = request.form.get("monto")
        tipo = request.form.get("tipo")
        archivo = request.files.get("comprobante")

        if not monto or not tipo:
            flash("Monto y tipo de pago son requeridos.", "danger")
            return redirect(request.url)

        try:
            pago = Pago(
                cliente_id=cliente.id,
                monto=float(monto),
                tipo=TipoPago[tipo.upper()],
                estado=EstadoPago.VALIDADO,
                fecha_pago=datetime.now(timezone.utc),
            )
            db.session.add(pago)
            db.session.flush()

            # 📎 Subida de comprobante opcional
            if archivo and archivo.filename:
                ext = os.path.splitext(archivo.filename)[1].lower()
                if ext not in [".jpg", ".jpeg", ".png", ".pdf"]:
                    flash("Formato no permitido.", "danger")
                    return redirect(request.url)

                filename = secure_filename(f"pago_{pago.id}_{datetime.utcnow():%Y%m%d%H%M%S}{ext}")
                ruta = os.path.join(get_dir(), filename)
                archivo.save(ruta)

                foto = Foto(
                    nombre_archivo=filename,
                    ruta=f"uploads/comprobantes/{filename}",
                    pago=pago,
                    uploaded_by=current_user.id
                )
                db.session.add(foto)

            db.session.commit()
            flash("Pago registrado correctamente", "success")

        except Exception as e:
            db.session.rollback()
            flash(f"Error: {e}", "danger")

        return redirect(url_for("pago.lista_pagos"))

    return render_template("admin/registrar_pago_admin.html", cliente=cliente)


# ===========================================================
#     🟢 VALIDAR/RECHAZAR PAGO
# ===========================================================
@pago_bp.route("/validar/<int:pago_id>", methods=["POST"])
@login_required
@roles_required("ADMIN")
def validar_pago(pago_id):
    pago = Pago.query.get_or_404(pago_id)
    cliente = pago.cliente
    accion = request.form.get("accion")

    try:
        if accion == "aprobar":
            pago.validar()
            cliente.fecha_ingreso = datetime.utcnow()
            cliente.membresia_vencimiento = cliente.fecha_ingreso + relativedelta(months=+1)
            cliente.estado_membresia = EstadoMembresia.ACTIVO
            flash("Pago aprobado y membresía actualizada.", "success")

        elif accion == "rechazar":
            pago.rechazar()
            flash("Pago rechazado.", "warning")

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        flash(f"Error: {e}", "danger")

    return redirect(url_for("pago.lista_pagos"))


# ===========================================================
#     🔄 Subir comprobante extra
# ===========================================================
@pago_bp.route("/comprobante/<int:pago_id>", methods=["GET", "POST"])
@login_required
def subir_comprobante(pago_id):
    pago = Pago.query.get_or_404(pago_id)

    if current_user.rol.nombre.upper() == "CLIENTE" and pago.cliente_id != current_user.cliente.id:
        abort(403)

    if request.method == "POST":
        archivo = request.files.get("comprobante")

        if archivo:
            ext = os.path.splitext(archivo.filename)[1].lower()
            if ext not in [".jpg", ".jpeg", ".png", ".pdf"]:
                flash("Formato no permitido.", "danger")
                return redirect(request.url)

            filename = secure_filename(f"pago_{pago.id}_{datetime.utcnow():%Y%m%d%H%M%S}{ext}")
            ruta = os.path.join(get_dir(), filename)
            archivo.save(ruta)

            try:
                foto = Foto(
                    nombre_archivo=filename,
                    ruta=f"uploads/comprobantes/{filename}",
                    pago=pago,
                    uploaded_by=current_user.id
                )
                db.session.add(foto)
                db.session.commit()

                flash("Archivo subido correctamente.", "success")

            except Exception as e:
                db.session.rollback()
                flash(f"Error: {e}", "danger")

            return redirect(url_for("cliente.detalles_cliente", id=pago.cliente_id))

    return render_template("cliente/subir_comprobante_pago.html", pago=pago)


# ===========================================================
#     🔥 EDITAR PAGO (ADMIN)
# ===========================================================
@pago_bp.route("/editar_admin/<int:pago_id>", methods=["GET","POST"])
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
            pago.tipo = TipoPago[tipo.upper()]

            # Si adjunta nuevo comprobante
            if archivo and archivo.filename:
                ext = os.path.splitext(archivo.filename)[1].lower()
                if ext not in [".jpg", ".jpeg", ".png", ".pdf"]:
                    flash("Formato no permitido.", "danger")
                    return redirect(request.url)

                filename = secure_filename(f"pago_{pago.id}_{datetime.utcnow():%Y%m%d%H%M%S}{ext}")
                archivo.save(os.path.join(get_dir(), filename))

                foto = Foto(
                    nombre_archivo=filename,
                    ruta=f"uploads/comprobantes/{filename}",
                    pago=pago,
                    uploaded_by=current_user.id
                )
                db.session.add(foto)

            db.session.commit()
            flash("Pago actualizado correctamente.", "success")

        except Exception as e:
            db.session.rollback()
            flash(f"Error: {e}", "danger")

        return redirect(url_for("pago.lista_pagos"))

    return render_template("admin/editar_pago_admin.html", pago=pago)


# ===========================================================
#     🟥 ELIMINAR PAGO
# ===========================================================
@pago_bp.route("/eliminar_admin/<int:pago_id>", methods=["POST"])
@login_required
@roles_required("ADMIN")
def eliminar_pago_admin(pago_id):
    pago = Pago.query.get_or_404(pago_id)

    try:
        db.session.delete(pago)
        db.session.commit()
        flash("Pago eliminado correctamente.", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Error: {e}", "danger")

    return redirect(url_for("pago.lista_pagos"))
