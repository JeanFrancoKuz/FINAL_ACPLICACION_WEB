import os
from flask import Flask, render_template
from config import Config
from extensions import db, login_manager
from models.usuarios import Usuario
from models.roles import Rol

# Blueprints
from routes.admin_routes import admin_bp
from routes.auth_routes import auth_bp
from routes.cliente_routes import cliente_bp
from routes.pago_routes import pago_bp
from routes.asistencia_routes import asistencia_bp
from routes.foto_routes import foto_bp
from routes.progreso_routes import progreso_bp
from routes.reportes_routes import reportes_bp


# ---------------------------------------------------
# APP FACTORY
# ---------------------------------------------------
def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

    # 🔹 Inicialización de extensiones
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id):
        return Usuario.query.get(int(user_id))

    # 🔹 Registro de Blueprints
    app.register_blueprint(admin_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(cliente_bp)
    app.register_blueprint(pago_bp)
    app.register_blueprint(asistencia_bp)
    app.register_blueprint(foto_bp)
    app.register_blueprint(progreso_bp)
    app.register_blueprint(reportes_bp)

    # Ruta principal pública
    @app.route("/")
    def index():
        return render_template("public/landing.html")

    # --- Inicializar BD + Roles + Admin ---
    with app.app_context():
        if not os.path.exists(app.instance_path):
            os.makedirs(app.instance_path, exist_ok=True)

        db.create_all()
        inicializar_roles_y_admin()

    # ---------------------------------------------------
    # MANEJO DE ERRORES 404 - 403 - 500
    # ---------------------------------------------------
    @app.errorhandler(404)
    def not_found(e):
        return render_template("errores/404.html"), 404

    @app.errorhandler(403)
    def no_autorizado(e):
        return render_template("errores/403.html"), 403

    @app.errorhandler(500)
    def error_servidor(e):
        return render_template("errores/500.html"), 500

    return app


# ---------------------------------------------------
# INICIALIZACIÓN AUTOMÁTICA DE ADMIN + ROLES
# ---------------------------------------------------
def inicializar_roles_y_admin():
    roles_requeridos = ["ADMIN", "CLIENTE"]
    existentes = Rol.query.with_entities(Rol.nombre).all()
    existentes = {r[0] for r in existentes}

    for nombre in roles_requeridos:
        if nombre not in existentes:
            db.session.add(Rol(nombre=nombre))

    db.session.commit()

    # Admin por defecto
    if not Usuario.query.filter_by(correo="admin@admin.com").first():
        admin = Usuario(
            nombre="Administrador",
            correo="admin@admin.com",
            cedula="00000000",
            rol=Rol.query.filter_by(nombre="ADMIN").first()
        )
        admin.set_password("12345")
        db.session.add(admin)
        db.session.commit()
        print("⚠ Usuario ADMIN creado: admin@admin.com / 12345")


# ---------------------------------------------------
if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
