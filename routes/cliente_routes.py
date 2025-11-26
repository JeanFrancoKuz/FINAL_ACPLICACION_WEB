import os
from datetime import datetime, date, timedelta, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from extensions import db
from models.clientes import Cliente, EstadoMembresia
from models.usuarios import Usuario
from models.roles import Rol
from models.fotos import Foto
from models.pagos import Pago, TipoPago, EstadoPago
from routes.decoradores import roles_required
from sqlalchemy.exc import IntegrityError
import secrets

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
# Lista de clientes (solo admin)
# ---------------------------
@cliente_bp.route("/lista")
@login_required
@roles_required("ADMIN")
def lista_clientes():
    q = request.args.get("q", "").strip()
    if q:
        clientes = Cliente.query.filter(
            (Cliente.nombre.ilike(f"%{q}%")) | (Cliente.cedula.ilike(f"%{q}%"))
        ).all()
    else:
        clientes = Cliente.query.all()
    return render_template("admin/lista_clientes.html", clientes=clientes)

# ---------------------------
# Crear cliente
# ---------------------------
# ---------- Crear cliente ----------
@cliente_bp.route("/crear", methods=["GET", "POST"])
@login_required
@roles_required("ADMIN")
def crear_cliente():
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        cedula = request.form.get("cedula", "").strip()
        correo = request.form.get("correo", "").strip().lower() or None
        telefono = request.form.get("telefono", "").strip()

        if not nombre or not cedula:
            flash("Nombre y cédula son obligatorios.", "danger")
            return redirect(url_for("cliente.crear_cliente"))

        # Crear usuario asociado AL CLIENTE (si no existe)
        if correo and Usuario.query.filter_by(correo=correo).first():
            flash("Ya existe un usuario con ese correo.", "danger")
            return redirect(url_for("cliente.crear_cliente"))

        # Buscar rol CLIENTE
        rol_cliente = Rol.query.filter_by(nombre="CLIENTE").first()
        if not rol_cliente:
            flash("Rol CLIENTE no encontrado. Contacta al administrador.", "danger")
            return redirect(url_for("cliente.crear_cliente"))

        # Generar contraseña temporal segura
        temp_password = secrets.token_urlsafe(8)

        try:
            nuevo_usuario = Usuario(
                nombre=nombre,
                correo=correo or f"{cedula}@local.invalid",  # si no hay correo, generar uno temporal
                cedula=cedula,
                rol=rol_cliente
            )
            nuevo_usuario.set_password(temp_password)
            db.session.add(nuevo_usuario)
            db.session.flush()  # para obtener nuevo_usuario.id

            # Crear cliente vinculado al usuario recién creado
            fecha_ingreso = date.today()
            membresia_vencimiento = fecha_ingreso + timedelta(days=30)

            nuevo_cliente = Cliente(
                nombre=nombre,
                cedula=cedula,
                telefono=telefono,
                correo=correo,
                fecha_ingreso=fecha_ingreso,
                estado_membresia=EstadoMembresia.ACTIVO,
                membresia_vencimiento=membresia_vencimiento,
                usuario_id=nuevo_usuario.id,
            )

            db.session.add(nuevo_cliente)
            db.session.commit()

            flash(
                f"Cliente registrado correctamente. Usuario creado (contraseña temporal enviada o visible por admin). Vence {membresia_vencimiento.strftime('%d-%m-%Y')}.",
                "success",
            )

            # Nota: en producción deberías enviar la contraseña temporal por email.
            # Para desarrollo la mostramos en consola (opcional)
            print(f"[DEBUG] temp user {nuevo_usuario.correo} password: {temp_password}")

        except Exception as e:
            db.session.rollback()
            flash(f"Error al crear cliente/usuario: {str(e)}", "danger")
            return redirect(url_for("cliente.crear_cliente"))

        return redirect(url_for("cliente.lista_clientes"))

    hoy = date.today().strftime("%d-%m-%Y")
    vence = (date.today() + timedelta(days=30)).strftime("%d-%m-%Y")
    return render_template("admin/crear_cliente.html", hoy=hoy, vence=vence)

# ---------------------------
# Editar cliente
# ---------------------------
@cliente_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@login_required
@roles_required("ADMIN")
def editar_cliente(id):
    cliente = Cliente.query.get_or_404(id)

    if request.method == "POST":
        cliente.nombre = request.form.get("nombre", "").strip()
        cliente.cedula = request.form.get("cedula", "").strip()
        cliente.correo = request.form.get("correo", "").strip().lower()
        cliente.telefono = request.form.get("telefono", "").strip()

        estado = request.form.get("estado_membresia", "")
        if estado and estado in EstadoMembresia.__members__:
            cliente.estado_membresia = EstadoMembresia[estado]

        fecha_vencimiento = request.form.get("membresia_vencimiento", "")
        if fecha_vencimiento:
            try:
                cliente.membresia_vencimiento = datetime.strptime(
                    fecha_vencimiento, "%Y-%m-%d"
                ).date()
            except ValueError:
                flash("Formato de fecha inválido.", "warning")

        if (
            cliente.membresia_vencimiento
            and cliente.membresia_vencimiento < date.today()
        ):
            cliente.estado_membresia = EstadoMembresia.VENCIDO

        try:
            db.session.commit()
            flash("Cliente actualizado correctamente.", "success")
        except IntegrityError as e:
            db.session.rollback()
            if "clientes.cedula" in str(e.orig):
                flash("Error: la cédula ya está registrada.", "danger")
            elif "clientes.correo" in str(e.orig):
                flash("Error: el correo ya está registrado.", "danger")
            else:
                flash("Error: no se pudo actualizar cliente.", "danger")

        return redirect(url_for("cliente.lista_clientes"))

    dias_restantes = None
    if cliente.membresia_vencimiento:
        dias_restantes = (cliente.membresia_vencimiento - date.today()).days

    return render_template(
        "admin/editar_cliente.html",
        cliente=cliente,
        dias_restantes=dias_restantes,
    )

# ---------------------------
# Eliminar cliente
# ---------------------------
@cliente_bp.route("/eliminar/<int:id>", methods=["POST"])
@login_required
@roles_required("ADMIN")
def eliminar_cliente(id):
    cliente = Cliente.query.get_or_404(id)
    try:
        db.session.delete(cliente)
        db.session.commit()
        flash("Cliente eliminado correctamente.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"No se pudo eliminar cliente: {str(e)}", "danger")
    return redirect(url_for("cliente.lista_clientes"))

# ---------------------------
# Detalles de cliente
# ---------------------------
@cliente_bp.route("/perfil/<int:id>")
@login_required
def detalles_cliente(id):
    cliente = Cliente.query.get_or_404(id)

    if current_user.rol.nombre.upper() == "CLIENTE" and current_user.cliente.id != id:
        flash("No tienes permiso para ver otro perfil.", "danger")
        return redirect(url_for("index"))

    fotos = Foto.query.filter_by(cliente_id=id).all()
    return render_template(
        "clientes/detalles_cliente.html",
        cliente=cliente,
        fotos=fotos,
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
# Validar comprobante (admin)
# ---------------------------
@cliente_bp.route("/validar_comprobante/<int:id>", methods=["POST"])
@login_required
@roles_required("ADMIN")
def validar_comprobante(id):
    cliente = Cliente.query.get_or_404(id)

    accion = request.form.get("accion")
    if accion == "aprobar":
        cliente.estado_membresia = EstadoMembresia.ACTIVO
        flash("Comprobante aprobado. Cliente activado.", "success")
    elif accion == "rechazar":
        cliente.estado_membresia = EstadoMembresia.INACTIVO
        flash("Comprobante rechazado. Cliente marcado como inactivo.", "danger")

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f"Error al validar comprobante: {str(e)}", "danger")
    return redirect(url_for("cliente.lista_clientes"))

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

