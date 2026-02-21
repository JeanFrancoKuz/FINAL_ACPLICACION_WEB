from datetime import datetime, date, time, timedelta, timezone
from flask import Blueprint, render_template, flash, redirect, url_for, request
from flask_login import login_required
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
import secrets

# Decorador
from routes.decoradores import roles_required

# Modelos
from models.clientes import Cliente, EstadoMembresia
from models.pagos import Pago, EstadoPago
from models.usuarios import Usuario
from models.roles import Rol
from models.fotos import Foto
from models.asistencias import Asistencia
from extensions import db

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# ---------------------------------------------------
# Dashboard
# ---------------------------------------------------
@admin_bp.route("/dashboard")
@login_required
@roles_required("ADMIN")
def dashboard():
    try:
        # --- Clientes ---
        clientes_activos = db.session.query(func.count(Cliente.id)).filter(
            Cliente.estado_membresia == EstadoMembresia.ACTIVO
        ).scalar()
        clientes_vencidos = db.session.query(func.count(Cliente.id)).filter(
            Cliente.estado_membresia == EstadoMembresia.VENCIDO
        ).scalar()

        # --- Pagos ---
        pagos_registrados = db.session.query(func.count(Pago.id)).scalar()
        pagos_pendientes = db.session.query(func.count(Pago.id)).filter(
            Pago.estado == EstadoPago.PENDIENTE
        ).scalar()

        # --- Asistencias ---
        hoy_iso = datetime.utcnow().date().isoformat()
        asistencias_hoy = db.session.query(func.count(Asistencia.id)).filter(
            db.func.date(Asistencia.fecha) == hoy_iso
        ).scalar()

    except Exception as e:
        flash(f"Error al generar métricas: {str(e)}", "danger")
        clientes_activos = clientes_vencidos = pagos_registrados = pagos_pendientes = asistencias_hoy = 0

    return render_template(
        "admin/dashboard.html",
        clientes_activos=clientes_activos,
        clientes_vencidos=clientes_vencidos,
        pagos_registrados=pagos_registrados,
        pagos_pendientes=pagos_pendientes,
        asistencias_hoy=asistencias_hoy
    )


# ---------------------------------------------------
# Enviar mensaje
# ---------------------------------------------------
@admin_bp.route("/enviar_mensaje/<int:cliente_id>")
@login_required
@roles_required("ADMIN")
def enviar_mensaje(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)

    if cliente.estado_membresia != EstadoMembresia.VENCIDO:
        flash("Solo se puede enviar mensaje a clientes con membresía vencida.", "warning")
        return redirect(url_for("admin.lista_clientes"))

    mensaje = f"""
Hola {cliente.nombre},

Notamos que tu membresía en HITO ALL SPORT ha vencido el {cliente.membresia_vencimiento.strftime('%d-%m-%Y')}.
Te invitamos a renovarla para continuar con tus entrenamientos y beneficios.

Para renovar tu membresía, por favor contáctanos al {cliente.telefono or 'correo: ' + cliente.correo}.

¡Te esperamos!
HITO ALL SPORT
"""
    print(f"[DEBUG] Mensaje enviado a {cliente.telefono or cliente.correo}:\n{mensaje}")
    flash(f"Mensaje de recordatorio enviado a {cliente.nombre}.", "success")
    return redirect(url_for("admin.lista_clientes"))

# ---------------------------------------------------
# Lista clientes
# ---------------------------------------------------
@admin_bp.route("/lista")
@login_required
@roles_required("ADMIN")
def lista_clientes():
    q = request.args.get("q", "").strip()
    estado = request.args.get("estado", "").strip()
    query = Cliente.query

    if q:
        query = query.filter(
            (Cliente.nombre.ilike(f"%{q}%")) |
            (Cliente.cedula.ilike(f"%{q}%")) |
            (Cliente.correo.ilike(f"%{q}%"))
        )
    if estado:
        try:
            query = query.filter_by(estado_membresia=EstadoMembresia[estado])
        except KeyError:
            pass

    clientes = query.all()
    return render_template("admin/lista_cliente_admin.html", clientes=clientes)

# ---------------------------------------------------
# Crear cliente
# ---------------------------------------------------
@admin_bp.route("/crear", methods=["GET", "POST"])
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
            return redirect(url_for("admin.crear_cliente"))

        if correo and Usuario.query.filter_by(correo=correo).first():
            flash("Ya existe un usuario con ese correo.", "danger")
            return redirect(url_for("admin.crear_cliente"))

        rol_cliente = Rol.query.filter_by(nombre="CLIENTE").first()
        if not rol_cliente:
            flash("Rol CLIENTE no encontrado. Contacta al administrador.", "danger")
            return redirect(url_for("admin.crear_cliente"))

        temp_password = secrets.token_urlsafe(8)

        try:
            nuevo_usuario = Usuario(
                nombre=nombre,
                correo=correo or f"{cedula}@local.invalid",
                cedula=cedula,
                rol=rol_cliente
            )
            nuevo_usuario.set_password(temp_password)
            db.session.add(nuevo_usuario)
            db.session.flush()

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
                usuario_id=nuevo_usuario.id
            )
            db.session.add(nuevo_cliente)
            db.session.commit()

            flash(
                f"Cliente registrado correctamente. Usuario creado. Vence {membresia_vencimiento.strftime('%d-%m-%Y')}.",
                "success",
            )
            print(f"[DEBUG] temp user {nuevo_usuario.correo} password: {temp_password}")

        except Exception as e:
            db.session.rollback()
            flash(f"Error al crear cliente/usuario: {str(e)}", "danger")
            return redirect(url_for("admin.crear_cliente"))

        return redirect(url_for("admin.lista_clientes"))

    hoy = date.today().strftime("%d-%m-%Y")
    vence = (date.today() + timedelta(days=30)).strftime("%d-%m-%Y")
    return render_template("admin/cliente_crear_admin.html", hoy=hoy, vence=vence)

# ---------------------------------------------------
# Editar cliente
# ---------------------------------------------------
@admin_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@login_required
@roles_required("ADMIN")
def editar_cliente(id):
    cliente = Cliente.query.get_or_404(id)

    if request.method == "POST":
        # Actualizar campos básicos
        cliente.nombre = request.form.get("nombre", "").strip()
        cliente.cedula = request.form.get("cedula", "").strip()
        cliente.correo = request.form.get("correo", "").strip().lower()
        cliente.telefono = request.form.get("telefono", "").strip()

        # Actualizar estado de membresía
        estado = request.form.get("estado_membresia", "")
        if estado and estado in EstadoMembresia.__members__:
            cliente.estado_membresia = EstadoMembresia[estado]

        # Actualizar fecha de vencimiento
        fecha_vencimiento = request.form.get("membresia_vencimiento", "")
        if fecha_vencimiento:
            try:
                # Convertir a date para evitar conflictos con datetime
                cliente.membresia_vencimiento = datetime.strptime(fecha_vencimiento, "%Y-%m-%d").date()
            except ValueError:
                flash("Formato de fecha inválido.", "warning")

        # Marcar como vencido si la fecha ya pasó
        if cliente.membresia_vencimiento and cliente.membresia_vencimiento < date.today():
            cliente.estado_membresia = EstadoMembresia.VENCIDO

        # Guardar cambios
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

        return redirect(url_for("admin.lista_clientes"))

    # Calcular días restantes correctamente
    dias_restantes = None
    if cliente.membresia_vencimiento:
        # Asegurarse de que sea date
        vencimiento = cliente.membresia_vencimiento
        if isinstance(vencimiento, datetime):
            vencimiento = vencimiento.date()
        dias_restantes = (vencimiento - date.today()).days

    return render_template(
        "admin/cliente_editar_admin.html",
        cliente=cliente,
        dias_restantes=dias_restantes
    )

# ---------------------------------------------------
# Eliminar cliente
# ---------------------------------------------------
@admin_bp.route("/eliminar/<int:id>", methods=["POST"])
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
    return redirect(url_for("admin.lista_clientes"))

# ---------------------------------------------------
# Validar comprobante
# ---------------------------------------------------
@admin_bp.route("/validar_comprobante/<int:id>", methods=["POST"])
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
    return redirect(url_for("admin.lista_clientes"))

# ---------------------------------------------------
# Detalles del cliente
# ---------------------------------------------------
@admin_bp.route("/detalle/<int:id>")
@login_required
@roles_required("ADMIN")
def cliente_detalle_admin(id):
    cliente = Cliente.query.get_or_404(id)

    # Foto de perfil (si existe)
    foto_perfil = Foto.query.filter_by(cliente_id=cliente.id, tipo='perfil').first()

    # Últimos pagos (podemos mostrar todos o limitar a los últimos 5)
    pagos = Pago.query.filter_by(cliente_id=cliente.id).order_by(Pago.fecha_pago.desc()).all()

    # Últimas asistencias
    asistencias = Asistencia.query.filter_by(cliente_id=cliente.id).order_by(Asistencia.fecha.desc()).all()

    return render_template(
        "admin/cliente_detalle_admin.html",
        cliente=cliente,
        foto_perfil=foto_perfil,
        pagos=pagos,
        asistencias=asistencias
    )
