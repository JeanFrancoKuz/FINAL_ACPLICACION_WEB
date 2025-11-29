from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user


# ================================================================
#   🔐 Decorador: Requiere rol específico
# ================================================================
def roles_required(*allowed_roles):
    """
    Permite acceso solo a usuarios autenticados con uno de los roles indicados.

    Ejemplo:
        @roles_required("ADMIN", "CLIENTE")
        def vista():
            ...
    """

    allowed_roles = {role.upper() for role in allowed_roles}

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):

            # Usuario no logueado
            if not current_user.is_authenticated:
                flash("Debes iniciar sesión.", "warning")
                return redirect(url_for("auth.login"))

            # Usuario sin rol o rol no autorizado
            if not current_user.rol or current_user.rol.nombre.upper() not in allowed_roles:
                flash("No tienes permiso para acceder aquí.", "danger")
                return redirect(url_for("index"))

            return func(*args, **kwargs)

        return wrapper

    return decorator



# ================================================================
#   🔒 Decorador: Cuenta Activa (is_active=True)
# ================================================================
def active_account_required(func):
    """
    Bloquea acceso a cuentas desactivadas o inactivas.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):

        if not current_user.is_authenticated:
            flash("Primero inicia sesión.", "warning")
            return redirect(url_for("auth.login"))

        if not current_user.is_active:
            flash("Tu cuenta está desactivada. Contacta al administrador.", "danger")
            return redirect(url_for("auth.login"))

        return func(*args, **kwargs)

    return wrapper



# ================================================================
#   🛡 Decorador combinado opcional
# ================================================================
def secured_route(*roles):
    """
    @secured_route("ADMIN")
    @secured_route("CLIENTE","ADMIN")
    -> Rol + Cuenta Activa
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):

            if not current_user.is_authenticated:
                flash("Debes iniciar sesión.", "warning")
                return redirect(url_for("auth.login"))

            if not current_user.is_active:
                flash("Cuenta desactivada. Contacta al administrador.", "danger")
                return redirect(url_for("auth.login"))

            if roles and current_user.rol.nombre.upper() not in {r.upper() for r in roles}:
                flash("Acceso denegado.", "danger")
                return redirect(url_for("index"))

            return func(*args, **kwargs)

        return wrapper

    return decorator
