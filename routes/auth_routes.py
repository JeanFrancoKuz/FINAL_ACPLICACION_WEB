# ===============================================================
#              AUTENTICACIÓN COMPLETA Y SEGURA
# ===============================================================

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime, timezone
from werkzeug.security import check_password_hash
from models.usuarios import Usuario
from extensions import db

auth_bp = Blueprint("auth", __name__, url_prefix="/auth", template_folder="../templates/auth")

# ===============================================================
# 🔐 LOGIN
# ===============================================================
@auth_bp.route("/login", methods=["GET","POST"])
def login():

    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        entrada = request.form.get("usuario","").strip().lower()
        password = request.form.get("password","")

        usuario = Usuario.query.filter(
            (Usuario.correo.ilike(entrada)) | (Usuario.cedula == entrada)
        ).first()

        if not usuario:
            flash("Usuario no encontrado ❌", "danger")
            return redirect(url_for("auth.login"))

        if not usuario.is_active:
            flash("Cuenta inactiva. Contacte administración ⚠", "warning")
            return redirect(url_for("auth.login"))

        if not check_password_hash(usuario.password_hash, password):
            flash("Contraseña incorrecta ❗", "danger")
            return redirect(url_for("auth.login"))

        # ✔ Login completo
        login_user(usuario)
        usuario.last_login = datetime.now(timezone.utc)
        db.session.commit()

        # 🚨 Primera vez → Debe cambiar clave SÍ o SÍ
        if usuario.primera_vez:
            flash("Debes cambiar tu contraseña antes de continuar 🔐", "warning")
            return redirect(url_for("auth.cambiar_password_inicio"))

        # Redirigir por rol
        return redirect(url_for(
            "admin.dashboard_admin" if usuario.rol.nombre=="ADMIN" else "cliente.dashboard_cliente"
        ))

    return render_template("auth/login.html")


# ===============================================================
# 🔄 PRIMER CAMBIO OBLIGATORIO
# ===============================================================
@auth_bp.route("/primer-cambio", methods=["GET","POST"])
@login_required
def cambiar_password_inicio():

    if not current_user.primera_vez:
        return redirect(url_for("index"))

    if request.method == "POST":
        nueva = request.form.get("password","").strip()

        if len(nueva) < 6:
            flash("La contraseña debe tener mínimo 6 caracteres ❗", "danger")
            return redirect(url_for("auth.cambiar_password_inicio"))

        current_user.set_password(nueva)
        current_user.primera_vez = False
        db.session.commit()

        flash("Contraseña actualizada exitosamente 🔥", "success")
        return redirect(url_for(
            "admin.dashboard_admin" if current_user.rol.nombre=="ADMIN" else "cliente.dashboard_cliente"
        ))

    return render_template("auth/primer_cambio_password.html")


# ===============================================================
# 🚪 LOGOUT
# ===============================================================
@auth_bp.route("/logout", methods=["POST","GET"])
@login_required
def logout():
    nombre = current_user.nombre
    logout_user()
    flash(f"Hasta pronto {nombre} 👋", "info")
    return redirect(url_for("auth.login"))


# ===============================================================
# 🔥 Recuperar contraseña — Solicitud
# ===============================================================
@auth_bp.route("/recuperar", methods=["GET","POST"])
def recuperar_password():

    if request.method == "POST":
        correo = request.form.get("correo").strip().lower()
        usuario = Usuario.query.filter_by(correo=correo).first()

        if not usuario:
            flash("No existe una cuenta con ese correo ❌", "danger")
            return redirect(url_for("auth.recuperar_password"))

        token = usuario.generar_token_recuperacion()
        db.session.commit()

        # ⛔ POR AHORA mostramos link — luego enviamos por correo
        flash(f"""
        🔐 Enlace para restablecer contraseña:<br>
        <a href='{request.host_url}auth/reset/{token}'>{request.host_url}auth/reset/{token}</a><br>
        ⏳ Válido por 30 min
        """, "info")

    return render_template("auth/recuperar_password.html")


# ===============================================================
# 🔐 Restablecer contraseña con token
# ===============================================================
@auth_bp.route("/reset/<token>", methods=["GET","POST"])
def reset_password(token):
    usuario = Usuario.query.filter_by(reset_token=token).first()

    if not usuario or not usuario.token_valido(token):
        flash("Enlace inválido o expirado ❌", "danger")
        return redirect(url_for("auth.recuperar_password"))

    if request.method == "POST":
        nueva = request.form.get("password")
        repetir = request.form.get("repetir")

        if nueva != repetir:
            flash("Las contraseñas no coinciden ❗", "warning")
            return redirect(request.url)

        usuario.set_password(nueva)
        usuario.reset_token = None
        usuario.reset_expira = None
        usuario.primera_vez = False
        db.session.commit()

        flash("Contraseña actualizada exitosamente ✔", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", usuario=usuario)
