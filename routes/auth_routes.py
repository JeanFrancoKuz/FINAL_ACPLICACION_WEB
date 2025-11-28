from flask import (Blueprint, render_template, redirect, url_for, flash, request)
from flask_login import (login_user, logout_user, login_required, current_user)
from datetime import datetime, timezone
from werkzeug.security import check_password_hash
from models.usuarios import Usuario
from extensions import db

auth_bp = Blueprint("auth", __name__)

# ---------- Login ----------
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

        if usuario and check_password_hash(usuario.password_hash, password):
            if not usuario.is_active:
                flash("Tu cuenta está desactivada. Contacta al administrador.", "danger")
                return redirect(url_for("auth.login"))

            login_user(usuario, remember=bool(request.form.get("remember_me")))
            usuario.last_login = datetime.now(timezone.utc)
            db.session.commit()
            flash(f"Bienvenido {usuario.nombre}", "success")

            rol = usuario.rol.nombre.upper()
            if rol == "ADMIN":
                return redirect(url_for("admin.dashboard"))
            elif rol == "CLIENTE":
                return redirect(url_for("cliente.dashboard_cliente"))
            else:
                return redirect(url_for("index"))

        flash("Credenciales incorrectas", "danger")
        

    return render_template("auth/login.html")

# ---------- Logout ----------
@auth_bp.route("/logout")
@login_required
def logout():
    nombre = current_user.nombre or "Usuario"
    logout_user()
    flash(f"Sesión cerrada correctamente. Hasta pronto {nombre}", "info")
    return redirect(url_for("index"))

# ---------- Reset‑Password Request ----------
@auth_bp.route("/reset_password_request", methods=["GET", "POST"])
def reset_password_request():
    if request.method == "POST":
        correo = request.form.get("correo", "").strip().lower()
        usuario = Usuario.query.filter_by(correo=correo).first()
        if usuario:
            # ⚠️ En producción deberías enviar un email con token seguro
            flash("Enlace de restablecimiento generado (demo con ID directo).", "info")
            return redirect(url_for("auth.reset_password", id=usuario.id))
        flash("No existe un usuario con ese correo.", "danger")

    return render_template("auth/reset_password_request.html")

# ---------- Reset‑Password (ID en la URL) ----------
@auth_bp.route("/reset_password/<int:id>", methods=["GET", "POST"])
def reset_password(id):
    usuario = Usuario.query.get_or_404(id)
    if request.method == "POST":
        nueva_password = request.form.get("password", "")
        if not nueva_password:
            flash("La contraseña no puede estar vacía.", "danger")
        else:
            usuario.set_password(nueva_password)
            db.session.commit()
            flash("Tu contraseña ha sido actualizada. Ya puedes iniciar sesión.", "success")
            return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", usuario=usuario)