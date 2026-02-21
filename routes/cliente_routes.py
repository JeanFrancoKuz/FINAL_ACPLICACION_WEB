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


# ********  Blueprint de clientes  ********
cliente_bp = Blueprint("cliente", __name__, url_prefix="/cliente")

# ------------- Helper minimal -------------
def get_comprobantes_dir():
    """Obtiene el directorio de comprobantes dentro de static."""
    comprobantes_dir = os.path.join(current_app.root_path, "static", "comprobantes")
    os.makedirs(comprobantes_dir, exist_ok=True)
    return comprobantes_dir

# ---------------------------
# Dashboard del cliente
# ---------------------------
@cliente_bp.route("/dashboard")
@login_required
@roles_required("CLIENTE")
def dashboard_cliente():
    """Panel principal del cliente con métricas básicas."""
    cliente = current_user.cliente

    # Ejemplo de métricas: asistencias y pagos pendientes
    asistencias_mes = len([
        a for a in cliente.asistencias
        if a.fecha.month == datetime.now().month and a.fecha.year == datetime.now().year
    ])
    pagos_pendientes = len([p for p in cliente.pagos if p.estado.value == "PENDIENTE"])

    return render_template(
        "clientes/dashboard_cliente.html",
        cliente=cliente,
        asistencias_mes=asistencias_mes,
        pagos_pendientes=pagos_pendientes,
    )


# ---------------------------
# Detalles de cliente
# ---------------------------
@cliente_bp.route("/perfil/<int:id>")
@login_required
def detalles_cliente(id):
    cliente = Cliente.query.get_or_404(id)

    # Restricción de permisos
    if current_user.rol.nombre.upper() == "CLIENTE" and current_user.cliente.id != id:
        flash("No tienes permiso para ver otro perfil.", "danger")
        return redirect(url_for("index"))

    # Obtener fotos del cliente
    fotos = Foto.query.filter_by(cliente_id=id).all()
    
    # Obtener pagos del cliente, ordenados por fecha
    pagos = Pago.query.filter_by(cliente_id=id).order_by(Pago.fecha_pago.desc()).all()

    return render_template(
        "clientes/clientes_detalles_cliente.html",  # <-- template correcto
        cliente=cliente,
        fotos=fotos,
        pagos=pagos  # <-- pasamos los pagos al template
    )

# ---------------------------
# Subir comprobante
# ---------------------------
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
                flash("Formato de archivo no permitido.", "danger")
                return redirect(url_for("cliente.subir_comprobante", id=cliente.id))

            nombre_archivo = secure_filename(
                f"comprobante_{cliente.id}_{date.today().strftime('%Y%m%d')}{ext}"
            )
            comprobantes_dir = get_comprobantes_dir()
            ruta_absoluta = os.path.join(comprobantes_dir, nombre_archivo)
            archivo.save(ruta_absoluta)

            # Crear un pago PENDIENTE (monto a definir por admin)
            try:
                nuevo_pago = Pago(
                    cliente_id=cliente.id,
                    monto=0.0,  # admin debe actualizar el monto real
                    tipo=TipoPago.TRANSFERENCIA,  # enum TRANSFERENCIA
                    estado=EstadoPago.PENDIENTE,
                    fecha_pago=datetime.utcnow()
                )
                db.session.add(nuevo_pago)
                db.session.flush()  # para obtener nuevo_pago.id

                # Crear la foto asociada al pago
                ruta_relativa = f"comprobantes/{nombre_archivo}"
                foto = Foto(
                    nombre_archivo=nombre_archivo,
                    ruta=ruta_relativa,
                    pago=nuevo_pago,
                    uploaded_by=current_user.id
                )
                db.session.add(foto)

                # Marcar cliente como PENDIENTE
                cliente.estado_membresia = EstadoMembresia.PENDIENTE

                db.session.commit()
                flash("Comprobante subido correctamente. Pago creado y pendiente de validación.", "success")
            except Exception as e:
                db.session.rollback()
                flash(f"Error al guardar comprobante y crear pago: {str(e)}", "danger")

            return redirect(url_for("cliente.detalles_cliente", id=cliente.id))

    return render_template("clientes/subir_comprobante.html", cliente=cliente)

# ---------------------------
# foto de perfil cliente
# ---------------------------
@cliente_bp.route("/subir_foto_perfil/<int:id>", methods=["GET", "POST"])
@login_required
@roles_required("CLIENTE")
def subir_foto_perfil(id):
    cliente = Cliente.query.get_or_404(id)

    if current_user.cliente.id != id:
        flash("No tienes permiso para cambiar la foto de otro cliente.", "danger")
        return redirect(url_for("index"))

    if request.method == "POST":
        archivo = request.files.get("foto")
        if archivo:
            ext = os.path.splitext(archivo.filename)[1].lower()
            if ext not in [".jpg", ".jpeg", ".png"]:
                flash("Formato de archivo no permitido.", "danger")
                return redirect(request.url)

            nombre_archivo = secure_filename(
                f"profile_{cliente.id}_{datetime.now(timezone.utc).strftime('%Y%m%d')}{ext}"
            )
            profile_dir = os.path.join(current_app.root_path, "static", "profile")
            os.makedirs(profile_dir, exist_ok=True)
            archivo.save(os.path.join(profile_dir, nombre_archivo))

            cliente.foto_perfil = f"profile/{nombre_archivo}"

            try:
                db.session.commit()
                flash("Foto de perfil actualizada correctamente.", "success")
            except Exception as e:
                db.session.rollback()
                flash(f"Error al guardar foto de perfil: {str(e)}", "danger")

            return redirect(url_for("cliente.detalles_cliente", id=id))

    return render_template("clientes/subir_foto_perfil.html", cliente=cliente)

