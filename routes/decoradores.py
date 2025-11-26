from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user

# --------------------------------------------------------------------------- #
# Role control decorator
# --------------------------------------------------------------------------- #
def roles_required(*allowed_roles):
    """
    Allow access only to authenticated users
    who have one of the specified roles.

    Example:
        @roles_required("ADMIN", "CLIENTE")
        def my_view():
            ...
    """
    allowed_roles = {role.upper() for role in allowed_roles}

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("You must log in to access.", "warning")
                return redirect(url_for("auth.login"))

            if (
                current_user.rol is None
                or current_user.rol.nombre.upper() not in allowed_roles
            ):
                flash("You do not have permission to access this section.", "danger")
                return redirect(url_for("index"))

            return func(*args, **kwargs)

        return wrapper

    return decorator


# --------------------------------------------------------------------------- #
# Active account decorator
# --------------------------------------------------------------------------- #
def active_account_required(func):
    """
    Ensure that the account is active (is_active=True).
    Assumes the user is already authenticated; if not,
    redirects to the login screen.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_active:
            flash("Your account is deactivated. Contact the administrator.", "danger")
            return redirect(url_for("auth.login"))
        return func(*args, **kwargs)

    return wrapper