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

# ---------------------------
# Lista de pagos (admin)
# ---------------------------

@pago_bp.route("/lista")
@login_required
@roles_required("ADMIN")   
def lista_pagos():
    estado = request.args.get("estado", "")
    q = request.args.get("q", "").strip()

    # Base query con join al cliente
    query = Pago.query.join(Cliente)

    # Filtrar por estado
    if estado:
        query = query.filter(Pago.estado == EstadoPago[estado.upper()])

    # Filtrar por nombre o cédula
    if q:
        query = query.filter(
            (Cliente.nombre.ilike(f"%{q}%")) | (Cliente.cedula.ilike(f"%{q}%"))
        )

    pagos = query.order_by(Pago.fecha_pago.desc()).all()
    return render_template("admin/lista_pagos_admin.html", pagos=pagos)

# ---------------------------
# Registrar pago (cliente)
# ---------------------------
@pago_bp.route("/registrar/<int:cliente_id>", methods=["GET", "POST"])
@login_required
def registrar_pago(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)

    # Solo el cliente dueño o admin pueden registrar
    if current_user.rol.nombre.upper() == "CLIENTE" and current_user.cliente.id != cliente_id:
        abort(403)

    if request.method == "POST":
        monto = request.form.get("monto")
        tipo = request.form.get("tipo")
        if not monto or not tipo:
            flash("Monto y tipo de pago son obligatorios.", "danger")
            return redirect(url_for("pago.registrar_pago", cliente_id=cliente_id))
        try:
            nuevo_pago = Pago(
                cliente_id=cliente.id,
                monto=float(monto),
                tipo=TipoPago[tipo.upper()],
                estado=EstadoPago.PENDIENTE,
                fecha_pago=datetime.now(timezone.utc)
            )
            db.session.add(nuevo_pago)
            db.session.commit()
            flash("Pago registrado correctamente. Pendiente de validación.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Error al registrar pago: {str(e)}", "danger")
        return redirect(url_for("cliente.detalles_cliente", id=cliente.id))

    return render_template("clientes/registrar_pago.html", cliente=cliente)

# ---------------------------
# Registrar pago directo (admin)
# ---------------------------

@pago_bp.route("/registrar_admin/<int:cliente_id>", methods=["GET", "POST"])
@login_required
@roles_required("ADMIN")
def registrar_pago_admin(cliente_id):
    # Si cliente_id = 0, mostrar selección de cliente con búsqueda
    if cliente_id == 0:
        q = request.args.get("q", "").strip()
        query = Cliente.query
        if q:
            query = query.filter(
                (Cliente.nombre.ilike(f"%{q}%")) |
                (Cliente.cedula.ilike(f"%{q}%"))
            )
        clientes = query.order_by(Cliente.nombre).all()
        return render_template("admin/seleccionar_cliente_pago.html", clientes=clientes, search=q)

    # Si se selecciona un cliente específico, mostrar formulario de registro
    cliente = Cliente.query.get_or_404(cliente_id)

    if request.method == "POST":
        monto = request.form.get("monto")
        tipo = request.form.get("tipo")
        archivo = request.files.get("comprobante")  # archivo opcional

        if not monto or not tipo:
            flash("Monto y tipo de pago son obligatorios.", "danger")
            return redirect(url_for("pago.registrar_pago_admin", cliente_id=cliente_id))

        try:
            nuevo_pago = Pago(
                cliente_id=cliente.id,
                monto=float(monto),
                tipo=TipoPago[tipo.upper()],
                estado=EstadoPago.VALIDADO,  # admin ya valida directamente
                fecha_pago=datetime.now(timezone.utc)
            )
            db.session.add(nuevo_pago)
            db.session.flush()  # para obtener el ID antes de commit

            # Si hay comprobante
            if archivo and archivo.filename != "":
                ext = os.path.splitext(archivo.filename)[1].lower()
                if ext not in [".jpg", ".jpeg", ".png", ".pdf"]:
                    flash("Formato de archivo no permitido.", "danger")
                    return redirect(request.url)

                nombre_archivo = secure_filename(
                    f"pago_{nuevo_pago.id}_{datetime.now(timezone.utc).strftime('%Y%m%d')}{ext}"
                )
                comprobantes_dir = os.path.join(current_app.root_path, "static", "comprobantes")
                os.makedirs(comprobantes_dir, exist_ok=True)
                archivo.save(os.path.join(comprobantes_dir, nombre_archivo))

                ruta_relativa = f"comprobantes/{nombre_archivo}"
                foto = Foto(
                    nombre_archivo=nombre_archivo,
                    ruta=ruta_relativa,
                    pago=nuevo_pago,
                    uploaded_by=current_user.id
                )
                db.session.add(foto)

            db.session.commit()
            flash("Pago registrado correctamente.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Error al registrar pago: {str(e)}", "danger")
        return redirect(url_for("pago.lista_pagos"))

    return render_template("admin/registrar_pago_admin.html", cliente=cliente)

# ---------------------------
# Validar o rechazar pago (admin)
# ---------------------------
@pago_bp.route("/validar/<int:pago_id>", methods=["POST"])
@login_required
@roles_required("ADMIN")   
def validar_pago(pago_id):
    pago = Pago.query.get_or_404(pago_id)
    cliente = pago.cliente
    accion = request.form.get("accion")
    try:
        if accion == "aprobar":
            pago.validar()  # cambia el estado a VALIDADO
            flash("Pago aprobado correctamente.", "success")

            # Actualizar fechas y estado del cliente correctamente
            cliente.fecha_ingreso = datetime.now(timezone.utc)
            cliente.membresia_vencimiento = cliente.fecha_ingreso + relativedelta(months=+1)
            cliente.estado_membresia = EstadoMembresia.ACTIVO

        elif accion == "rechazar":
            pago.rechazar()
            flash("Pago rechazado.", "danger")

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f"Error al validar pago: {str(e)}", "danger")

    return redirect(url_for("pago.lista_pagos"))
# ---------------------------
# Subir comprobante (cliente)
# ---------------------------
@pago_bp.route("/comprobante/<int:pago_id>", methods=["GET", "POST"])
@login_required
def subir_comprobante(pago_id):
    pago = Pago.query.get_or_404(pago_id)

    # Solo el cliente dueño o admin pueden subir comprobante
    if current_user.rol.nombre.upper() == "CLIENTE" and current_user.cliente.id != pago.cliente_id:
        abort(403)

    if request.method == "POST":
        archivo = request.files.get("comprobante")
        if archivo:
            ext = os.path.splitext(archivo.filename)[1].lower()
            if ext not in [".jpg", ".jpeg", ".png", ".pdf"]:
                flash("Formato de archivo no permitido.", "danger")
                return redirect(request.url)

            nombre_archivo = secure_filename(
                f"pago_{pago.id}_{datetime.now(timezone.utc).strftime('%Y%m%d')}{ext}"
            )
            comprobantes_dir = os.path.join(current_app.root_path, "static", "comprobantes")
            os.makedirs(comprobantes_dir, exist_ok=True)
            archivo.save(os.path.join(comprobantes_dir, nombre_archivo))

            ruta_relativa = f"comprobantes/{nombre_archivo}"

            try:
                foto = Foto(
                    nombre_archivo=nombre_archivo,
                    ruta=ruta_relativa,
                    pago=pago,
                    uploaded_by=current_user.id
                )
                db.session.add(foto)
                db.session.commit()
                flash("Comprobante subido correctamente. El admin revisará tu pago.", "success")
            except Exception as e:
                db.session.rollback()
                flash(f"Error al subir comprobante: {str(e)}", "danger")
            return redirect(url_for("cliente.detalles_cliente", id=pago.cliente_id))
    return render_template("clientes/subir_comprobante_pago.html", pago=pago)

# Editar pago
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
            flash("Monto y tipo de pago son obligatorios.", "danger")
            return redirect(request.url)

        try:
            pago.monto = float(monto)
            pago.tipo = TipoPago[tipo.upper()]

            if archivo and archivo.filename != "":
                ext = os.path.splitext(archivo.filename)[1].lower()
                if ext not in [".jpg", ".jpeg", ".png", ".pdf"]:
                    flash("Formato de archivo no permitido.", "danger")
                    return redirect(request.url)

                nombre_archivo = secure_filename(
                    f"pago_{pago.id}_{datetime.now(timezone.utc).strftime('%Y%m%d')}{ext}"
                )
                comprobantes_dir = os.path.join(current_app.root_path, "static", "comprobantes")
                os.makedirs(comprobantes_dir, exist_ok=True)
                archivo.save(os.path.join(comprobantes_dir, nombre_archivo))

                ruta_relativa = f"comprobantes/{nombre_archivo}"
                foto = Foto(
                    nombre_archivo=nombre_archivo,
                    ruta=ruta_relativa,
                    pago=pago,
                    uploaded_by=current_user.id
                )
                db.session.add(foto)

            db.session.commit()
            flash("Pago actualizado correctamente.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Error al actualizar pago: {str(e)}", "danger")
        return redirect(url_for("pago.lista_pagos"))

    return render_template("admin/editar_pago_admin.html", pago=pago)


# Eliminar pago
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
        flash(f"Error al eliminar pago: {str(e)}", "danger")
    return redirect(url_for("pago.lista_pagos"))
