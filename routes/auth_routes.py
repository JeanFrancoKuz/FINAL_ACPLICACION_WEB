from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime, timezone
from werkzeug.security import check_password_hash
from models.usuarios import Usuario
from extensions import db

auth_bp = Blueprint(
    "auth", __name__, url_prefix="/auth", template_folder="../templates/auth"
)

# ───────────────────────── LOGIN ───────────────────────── #
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        entrada = request.form.get("usuario", "").strip().lower()
        password = request.form.get("password", "")

        usuario = Usuario.query.filter(
            (Usuario.correo.ilike(entrada)) | (Usuario.cedula == entrada)
        ).first()

        if not usuario:
            flash("Usuario no encontrado.", "danger")
            return redirect(url_for("auth.login"))

        if not usuario.is_active:
            flash("Cuenta desactivada. Contacta soporte.", "warning")
            return redirect(url_for("auth.login"))

        if not check_password_hash(usuario.password_hash, password):
            flash("Contraseña incorrecta.", "danger")
            return redirect(url_for("auth.login"))

        # 🔥 LOGIN exitoso
        login_user(usuario, remember="remember_me" in request.form)
        usuario.last_login = datetime.now(timezone.utc)
        db.session.commit()

        flash(f"Bienvenido {usuario.nombre}", "success")

        # 🚨 Si es su primer ingreso → obligamos a cambiar clave
        if usuario.primera_vez:
            return redirect(url_for("auth.cambiar_password_inicio"))

        # Redirecciones por Rol
        match usuario.rol.nombre.upper():
            case "ADMIN":
                return redirect(url_for("admin.dashboard_admin"))
            case "CLIENTE":
                return redirect(url_for("cliente.dashboard_cliente"))
            case _:
                return redirect(url_for("index"))

    return render_template("auth/login.html")


# ───────────────────────── CAMBIO DE CONTRASEÑA PRIMER ACCESO ───────────────────────── #
@auth_bp.route("/primer-cambio", methods=["GET","POST"])
@login_required
def cambiar_password_inicio():

    # Solo debe acceder si tiene clave temporal
    if not current_user.primera_vez:
        return redirect(url_for("index"))

    if request.method == "POST":
        nueva = request.form.get("password","").strip()

        if len(nueva) < 6:
            flash("La nueva contraseña debe tener mínimo 6 caracteres.", "danger")
            return redirect(url_for("auth.cambiar_password_inicio"))

        current_user.set_password(nueva)
        current_user.primera_vez = False  # 🚀 ya no volverá aquí
        db.session.commit()

        flash("Contraseña guardada con éxito. Bienvenido 👏", "success")

        if current_user.rol.nombre.upper() == "ADMIN":
            return redirect(url_for("admin.dashboard_admin"))
        else:
            return redirect(url_for("cliente.dashboard_cliente"))

    return render_template("auth/primer_cambio_password.html")


# ───────────────────────── LOGOUT ───────────────────────── #
@auth_bp.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    nombre = current_user.nombre
    logout_user()
    flash(f"Hasta pronto, {nombre}. Sesión cerrada.", "info")
    return redirect(url_for("auth.login"))



# ───────────────────────── RESET PASSWORD REQUEST ───────────────────────── #
@auth_bp.route("/reset", methods=["GET", "POST"])
def reset_password_request():
    if request.method == "POST":
        correo = request.form.get("correo", "").strip().lower()
        usuario = Usuario.query.filter_by(correo=correo).first()

        if usuario:
            return redirect(url_for("auth.reset_password", id=usuario.id))

        flash("No existe un usuario registrado con ese correo.", "danger")

    return render_template("auth/reset_password_request.html")


# ───────────────────────── RESET PASSWORD (DEMO) ───────────────────────── #
@auth_bp.route("/reset/<int:id>", methods=["GET", "POST"])
def reset_password(id):
    usuario = Usuario.query.get_or_404(id)

    if request.method == "POST":
        nueva = request.form.get("password", "")
        if not nueva:
            flash("La contraseña no puede estar vacía.", "danger")
        else:
            usuario.set_password(nueva)
            db.session.commit()
            flash("Contraseña actualizada correctamente.", "success")
            return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", usuario=usuario)
