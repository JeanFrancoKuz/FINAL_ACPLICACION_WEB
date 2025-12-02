import os
from datetime import datetime
from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash, current_app
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from dateutil.relativedelta import relativedelta

from extensions import db
from models.pagos import Pago, EstadoPago, TipoPago, PlanPago
from models.clientes import Cliente, EstadoMembresia
from models.fotos import Foto
from routes.decoradores import roles_required


pago_bp = Blueprint("pago", __name__, url_prefix="/pagos")


# ===========================================================
# 📁 Carpeta comprobantes
# ===========================================================
def get_dir():
    ruta = os.path.join(current_app.root_path, "static", "uploads", "comprobantes")
    os.makedirs(ruta, exist_ok=True)
    return ruta


# ===========================================================
# ███ ADMIN – LISTA DE PAGOS
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
            flash("Estado inválido.", "warning")

    if q:
        query = query.filter(
            Cliente.nombre.ilike(f"%{q}%") |
            Cliente.cedula.ilike(f"%{q}%")
        )

    pagos = query.order_by(Pago.fecha_pago.desc()).all()
    return render_template("admin/lista_pagos_admin.html", pagos=pagos)


# ===========================================================
# ➕ Registrar pago (ADMIN)
# ===========================================================
@pago_bp.route("/registrar_admin/<int:cliente_id>", methods=["GET", "POST"])
@login_required
@roles_required("ADMIN")
def registrar_pago_admin(cliente_id):

    # Selección de cliente
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
        plan = request.form.get("plan")
        descripcion = request.form.get("descripcion")
        archivo = request.files.get("comprobante")

        if not monto or not tipo or not plan:
            flash("Monto, tipo y plan requeridos.", "danger")
            return redirect(request.url)

        try:
            pago = Pago(
                cliente_id=cliente.id,
                monto=float(monto),
                tipo=TipoPago[tipo.upper()],
                plan=PlanPago[plan.upper()],
                descripcion=descripcion,
                estado=EstadoPago.PENDIENTE,
                fecha_pago=datetime.utcnow()
            )
            db.session.add(pago)
            db.session.flush()   # obtiene pago.id

            # 📸 Guardar archivo
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
                    cliente_id=cliente.id,
                    uploaded_by=current_user.id
                ))

            db.session.commit()
            flash("Pago registrado ✔", "success")

        except Exception as e:
            db.session.rollback()
            flash(f"Error: {e}", "danger")

        return redirect(url_for("pago.lista_pagos"))

    return render_template("admin/registrar_pago_admin.html", cliente=cliente)


# ===========================================================
# ✏ Editar pago (ADMIN)
# ===========================================================
@pago_bp.route("/editar_admin/<int:pago_id>", methods=["GET", "POST"])
@login_required
@roles_required("ADMIN")
def editar_pago_admin(pago_id):
    pago = Pago.query.get_or_404(pago_id)
    cliente = pago.cliente

    if request.method == "POST":
        monto = request.form.get("monto")
        tipo = request.form.get("tipo")
        plan = request.form.get("plan")
        descripcion = request.form.get("descripcion")
        archivo = request.files.get("comprobante")

        if not monto or not tipo or not plan:
            flash("Monto, tipo y plan requeridos.", "danger")
            return redirect(request.url)

        try:
            pago.monto = float(monto)
            pago.tipo = TipoPago[tipo.upper()]
            pago.plan = PlanPago[plan.upper()]
            pago.descripcion = descripcion

            # 📸 si hay nuevo archivo
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
                    cliente_id=cliente.id,
                    uploaded_by=current_user.id
                ))

            db.session.commit()
            flash("Pago actualizado ✔", "success")

        except Exception as e:
            db.session.rollback()
            flash(f"Error: {e}", "danger")

        return redirect(url_for("pago.lista_pagos"))

    return render_template("admin/editar_pago_admin.html", pago=pago)


# ===========================================================
# 🧾 Validar pago (ADMIN)
# ===========================================================
@pago_bp.route("/validar/<int:pago_id>", methods=["POST"])
@login_required
@roles_required("ADMIN")
def validar_pago(pago_id):
    pago = Pago.query.get_or_404(pago_id)
    cliente = pago.cliente

    try:
        pago.estado = EstadoPago.VALIDADO

        hoy = datetime.utcnow()
        if not cliente.membresia_vencimiento or cliente.membresia_vencimiento < hoy:
            cliente.activar_membresia(30)
        else:
            cliente.membresia_vencimiento += relativedelta(days=30)
            cliente.estado_membresia = EstadoMembresia.ACTIVO

        db.session.commit()
        flash("Pago validado ✔", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Error al validar pago: {e}", "danger")

    return redirect(url_for("pago.lista_pagos"))


# ===========================================================
# 🧾 Rechazar pago (ADMIN)
# ===========================================================
@pago_bp.route("/rechazar/<int:pago_id>", methods=["POST"])
@login_required
@roles_required("ADMIN")
def rechazar_pago(pago_id):
    pago = Pago.query.get_or_404(pago_id)

    try:
        pago.estado = EstadoPago.RECHAZADO
        db.session.commit()
        flash("Pago rechazado ❌", "warning")

    except Exception as e:
        db.session.rollback()
        flash(f"Error al rechazar pago: {e}", "danger")

    return redirect(url_for("pago.lista_pagos"))


# ===========================================================
# 🗑 Eliminar pago (ADMIN)
# ===========================================================
@pago_bp.route("/eliminar/<int:pago_id>", methods=["POST"])
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
        flash(f"Error al eliminar pago: {e}", "danger")

    return redirect(url_for("pago.lista_pagos"))


# ===========================================================
# ███ CLIENTE
# ===========================================================
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
# 🟩 Registrar pago manual (CLIENTE)
# ---------------------------------------------------------
@pago_bp.route("/cliente/registrar", methods=["GET", "POST"])
@login_required
@roles_required("CLIENTE")
def registrar_pago_cliente():
    cliente = current_user.cliente

    monto_sugerido = request.args.get("bs", type=float)
    plan = request.args.get("plan", default="")
    descripcion = request.args.get("desc", default="")

    if request.method == "POST":

        monto = request.form.get("monto")
        tipo = request.form.get("tipo")
        plan_form = request.form.get("plan") or plan
        descripcion_form = request.form.get("descripcion") or descripcion
        archivo = request.files.get("comprobante")

        if not monto or not tipo or not plan_form:
            flash("Monto, tipo y plan requeridos.", "danger")
            return redirect(request.url)

        try:
            pago = Pago(
                cliente_id=cliente.id,
                monto=float(monto),
                tipo=TipoPago[tipo.upper()],
                plan=PlanPago[plan_form.upper()],
                descripcion=descripcion_form,
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
                    cliente_id=cliente.id,
                    uploaded_by=current_user.id
                ))

            db.session.commit()
            flash("Pago enviado ✔ Pendiente de validación", "success")

        except Exception as e:
            db.session.rollback()
            flash(f"Error: {e}", "danger")

        return redirect(url_for("pago.historial_pagos_cliente"))

    return render_template(
        "cliente/registrar_pago_cliente.html",
        cliente=cliente,
        monto_sugerido=monto_sugerido,
        plan=plan,
        descripcion=descripcion
    )


# ===========================================================
# 🟨 Historial completo cliente
# ===========================================================
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
