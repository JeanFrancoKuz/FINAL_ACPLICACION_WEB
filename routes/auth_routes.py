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

        # 🔥 Login exitoso
        login_user(usuario, remember="remember_me" in request.form)

        usuario.last_login = datetime.now(timezone.utc)
        db.session.commit()
        flash(f"Bienvenido {usuario.nombre}", "success")

        # Redirecciones por rol
        match usuario.rol.nombre.upper():
            case "ADMIN":
                return redirect(url_for("admin.dashboard_admin"))
            case "CLIENTE":
                return redirect(url_for("cliente.dashboard_cliente"))
            case _:
                return redirect(url_for("index"))

    return render_template("auth/login.html")


# ───────────────────────── LOGOUT ───────────────────────── #
@auth_bp.route("/logout")
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
            # 🔥 En producción se reemplaza por token seguro con Flask-Mail
            return redirect(url_for("auth.reset_password", id=usuario.id))

        flash("No existe un usuario registrado con ese correo.", "danger")

    return render_template("auth/reset_password_request.html")


# ───────────────────────── RESET PASSWORD (DIRECTO POR DEMO) ───────────────────────── #
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
