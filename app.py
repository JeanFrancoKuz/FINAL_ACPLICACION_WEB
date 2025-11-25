# app.py
from flask import Flask
from config import Config
from extensions import db, login_manager

# Importar blueprints directamente desde routes/
from routes.admin_routes import admin_bp
from routes.auth_routes import auth_bp
from routes.cliente_routes import cliente_bp
from routes.pago_routes import pago_bp
from routes.asistencia_routes import asistencia_bp
from routes.clase_routes import clase_bp
from routes.foto_routes import foto_bp

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

    # Inicializar extensiones
    db.init_app(app)
    login_manager.init_app(app)

    # Registrar blueprints
    app.register_blueprint(admin_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(cliente_bp)
    app.register_blueprint(pago_bp)
    app.register_blueprint(asistencia_bp)
    app.register_blueprint(clase_bp)
    app.register_blueprint(foto_bp)

    @app.route("/")
    def index():
        return "Aplicación Web Universidad - Proyecto Local"

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)