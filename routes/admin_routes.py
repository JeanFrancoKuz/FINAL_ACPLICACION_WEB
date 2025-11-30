from datetime import datetime, date, timedelta, timezone
from flask import Blueprint, render_template, flash, redirect, url_for, request
from flask_login import login_required
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
import secrets

from routes.decoradores import roles_required

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
def dashboard_admin():
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

        # --- Asistencias hoy ---
        hoy = date.today()
        asistencias_hoy = db.session.query(func.count(Asistencia.id)).filter(
            func.date(Asistencia.fecha) == hoy
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
        asistencias_hoy=asistencias_hoy,
    )


# ---------------------------------------------------
# Enviar mensaje a cliente vencido (simulado)
# ---------------------------------------------------
@admin_bp.route("/enviar_mensaje/<int:cliente_id>")
@login_required
@roles_required("ADMIN")
def enviar_mensaje(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)

    if cliente.estado_membresia != EstadoMembresia.VENCIDO:
        flash("Solo se puede enviar mensaje a clientes con membresía vencida.", "warning")
        return redirect(url_for("admin.lista_clientes"))

    venc = cliente.membresia_vencimiento.strftime("%d-%m-%Y") if cliente.membresia_vencimiento else "N/A"

    mensaje = f"""
Hola {cliente.nombre},

Notamos que tu membresía en HITO ALL SPORT ha vencido el {venc}.
Te invitamos a renovarla para continuar con tus entrenamientos y beneficios.

Para renovar tu membresía, por favor contáctanos al {cliente.telefono or ('correo: ' + (cliente.correo or 'N/D'))}.

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
            flash("Estado de membresía inválido.", "warning")

    clientes = query.order_by(Cliente.nombre.asc()).all()
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
            # Crear usuario vinculado
            nuevo_usuario = Usuario(
                nombre=nombre,
                correo=correo or f"{cedula}@local.invalid",
                cedula=cedula,
                rol=rol_cliente,
                primera_vez=True
            )
            nuevo_usuario.set_password(temp_password)
            db.session.add(nuevo_usuario)
            db.session.flush()  # para obtener nuevo_usuario.id

            # Crear cliente + activar membresía inicial
            nuevo_cliente = Cliente(
                nombre=nombre,
                cedula=cedula,
                telefono=telefono,
                correo=correo,
                usuario_id=nuevo_usuario.id,
            )
            # usamos lógica del modelo
            nuevo_cliente.activar_membresia(duracion_dias=30)

            db.session.add(nuevo_cliente)
            db.session.commit()

            flash(
                    f"Cliente creado ✔ | Usuario: <b>{nuevo_usuario.correo}</b> | Contraseña temporal: "
                    f"<b style='color:#ffeb3b'>{temp_password}</b><br>"
                    f"⚠ Recomienda al cliente cambiarla al iniciar sesión.",
                    "info"
                )


        except Exception as e:
            db.session.rollback()
            flash(f"Error al crear cliente/usuario: {str(e)}", "danger")
            return redirect(url_for("admin.crear_cliente"))

        db.session.commit()

        #  ➜ MOSTRAR CREDENCIALES VISUALMENTE
        return render_template("admin/credenciales_generadas.html",
                        usuario=nuevo_usuario.correo,
                        password=temp_password,
                        vence=nuevo_cliente.membresia_vencimiento.strftime('%d-%m-%Y'))


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
        cliente.nombre = request.form.get("nombre", "").strip()
        cliente.cedula = request.form.get("cedula", "").strip()
        cliente.correo = request.form.get("correo", "").strip().lower() or None
        cliente.telefono = request.form.get("telefono", "").strip()

        estado = request.form.get("estado_membresia", "")
        if estado and estado in EstadoMembresia.__members__:
            cliente.estado_membresia = EstadoMembresia[estado]

        fecha_vencimiento = request.form.get("membresia_vencimiento", "")
        if fecha_vencimiento:
            try:
                # almacenamos como datetime con zona UTC para ser consistentes
                dt = datetime.strptime(fecha_vencimiento, "%Y-%m-%d")
                cliente.membresia_vencimiento = dt.replace(tzinfo=timezone.utc)
            except ValueError:
                flash("Formato de fecha inválido. Usa AAAA-MM-DD.", "warning")

        # Actualizar estado según vencimiento
        if cliente.membresia_vencimiento:
            # si ya venció, marcar como VENCIDO
            if cliente.membresia_vencimiento < datetime.now(timezone.utc):
                cliente.estado_membresia = EstadoMembresia.VENCIDO

        try:
            db.session.commit()
            flash("Cliente actualizado correctamente.", "success")
        except IntegrityError as e:
            db.session.rollback()
            msg = str(e.orig)
            if "clientes.cedula" in msg:
                flash("Error: la cédula ya está registrada.", "danger")
            elif "clientes.correo" in msg:
                flash("Error: el correo ya está registrado.", "danger")
            else:
                flash("Error al actualizar cliente.", "danger")

        return redirect(url_for("admin.lista_clientes"))

    # Días restantes (usando método del modelo si quieres)
    dias_restantes = cliente.dias_restantes()

    return render_template(
        "admin/cliente_editar_admin.html",
        cliente=cliente,
        dias_restantes=dias_restantes,
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
# Validar comprobante (muy básico)
# ---------------------------------------------------
from datetime import timedelta

@admin_bp.route("/validar_comprobante/<int:id>", methods=["POST"])
@login_required
@roles_required("ADMIN")
def validar_comprobante(id):
    cliente = Cliente.query.get_or_404(id)
    accion = request.form.get("accion")

    if accion == "aprobar":

        # Activar estado de membresía
        cliente.estado_membresia = EstadoMembresia.ACTIVO

        # Si no tiene fecha o ya venció → la activamos por un mes desde hoy
        if not cliente.membresia_vencimiento or cliente.membresia_vencimiento < date.today():
            cliente.membresia_vencimiento = date.today() + timedelta(days=30)
        else:
            # Si el cliente aún tiene días activos → se le suma otro mes
            cliente.membresia_vencimiento += timedelta(days=30)

        flash("Membresía renovada +1 mes ✔", "success")

    elif accion == "rechazar":
        cliente.estado_membresia = EstadoMembresia.INACTIVO
        flash("Comprobante rechazado. El cliente queda inactivo.", "warning")

    else:
        flash("Acción no válida.", "danger")

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

    # ⚠ En el modelo Foto NO existe campo 'tipo'.
    # Para "foto de perfil" usamos el campo foto_perfil del cliente si existe.
    foto_perfil = cliente.foto_perfil

    pagos = Pago.query.filter_by(cliente_id=cliente.id).order_by(Pago.fecha_pago.desc()).all()
    asistencias = Asistencia.query.filter_by(cliente_id=cliente.id).order_by(Asistencia.fecha.desc()).all()

    return render_template(
        "admin/cliente_detalle_admin.html",
        cliente=cliente,
        foto_perfil=foto_perfil,
        pagos=pagos,
        asistencias=asistencias,
    )
