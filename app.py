import os
from flask import Flask, render_template
from config import Config
from extensions import db, login_manager
from models.usuarios import Usuario
from models.roles import Rol

# Blueprints …
from routes.admin_routes import admin_bp
from routes.auth_routes import auth_bp
from routes.cliente_routes import cliente_bp
from routes.pago_routes import pago_bp
from routes.asistencia_routes import asistencia_bp
from routes.foto_routes import foto_bp
from routes.progreso_routes import progreso_bp
from routes.reportes_routes import reportes_bp

# … (importas los demás)

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

    # Inicializa extensiones
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id):
        return Usuario.query.get(int(user_id))

    # Registra blueprints
    for bp in (admin_bp, auth_bp, cliente_bp, pago_bp,
            asistencia_bp, foto_bp, progreso_bp, reportes_bp):
        app.register_blueprint(bp)

    @app.route("/")
    def index():
        return render_template('public/landing.html')

    # --- Inicialización de BD y roles ---
    with app.app_context():
        # 1. asegura que el directorio `instance/` exista
        if not os.path.isdir(app.instance_path):
            os.makedirs(app.instance_path, exist_ok=True)

        # 2. crea las tablas que aún no existen
        db.create_all()

        # 3. roles
        def _ensure_roles(session):
            required = {"ADMIN", "CLIENTE"}
            existing = {r.nombre for r in session.query(Rol).filter(Rol.nombre.in_(required)).all()}
            for name in required - existing:
                session.add(Rol(nombre=name))
            if required - existing:
                session.commit()
                print("Roles creados:", ','.join(required - existing))

        _ensure_roles(db.session)

        # 4. usuario admin
        if not Usuario.query.filter_by(correo="admin@admin.com").first():
            admin_role = Rol.query.filter_by(nombre="ADMIN").first()
            admin_user = Usuario(
                nombre="Fabiola",
                correo="admin@admin.com",
                cedula="00000000",
                rol=admin_role
            )
            admin_user.set_password("12345")
            db.session.add(admin_user)
            try:
                db.session.commit()
                print("Usuario administrador creado.")
            except Exception as e:
                db.session.rollback()
                print("Error al crear usuario admin:", e)

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
