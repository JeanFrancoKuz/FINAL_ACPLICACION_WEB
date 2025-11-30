from datetime import datetime, timedelta
from typing import Optional
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import validates
from extensions import db


class Usuario(UserMixin, db.Model):
    __tablename__ = "usuarios"
    __table_args__ = (
        db.UniqueConstraint("correo", name="uq_usuario_correo"),
        db.UniqueConstraint("cedula", name="uq_usuario_cedula"),
        db.Index("ix_usuario_rol_id", "rol_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    correo = db.Column(db.String(120), nullable=False, index=True)
    cedula = db.Column(db.String(20), nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    primera_vez = db.Column(db.Boolean, default=True, nullable=False)
    last_login = db.Column(db.DateTime, default=None, index=True)

    # 🔥 Campos añadidos para recuperación segura
    reset_token = db.Column(db.String(255), unique=True, nullable=True)
    reset_expira = db.Column(db.DateTime, nullable=True)

    rol_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False, index=True)
    rol = db.relationship("Rol", back_populates="usuarios")

    cliente = db.relationship("Cliente", back_populates="usuario", uselist=False)

    fotos = db.relationship(
        "Foto",
        back_populates="usuario",
        cascade="all, delete-orphan",
        lazy="select"
    )


    # --------------------------- Validaciones
    @validates("correo")
    def validate_correo(self, key, value):
        if not value or "@" not in value or "." not in value:
            raise ValueError("Correo inválido")
        return value.lower()

    @validates("cedula")
    def validate_cedula(self, key, value):
        if not value or not value.isdigit():
            raise ValueError("La cédula debe contener solo números")
        if len(value) >20:
            raise ValueError("Cédula excede el máximo permitido (20)")
        return value


    # --------------------------- Seguridad
    def set_password(self, pwd):
        if not pwd:
            raise ValueError("La contraseña no puede ser vacía")
        self.password_hash = generate_password_hash(pwd)

    def check_password(self, pwd):
        return check_password_hash(self.password_hash, pwd)

    @property
    def password(self):
        raise AttributeError("La contraseña no se puede visualizar.")


    # --------------------------- Recuperación de contraseña
    def generar_token_recuperacion(self):
        """Genera token y lo almacena con expiración de 30 min."""
        import secrets
        token = secrets.token_urlsafe(32)
        self.reset_token = token
        self.reset_expira = datetime.utcnow() + timedelta(minutes=30)
        return token

    def token_valido(self, token):
        """Confirma que el token pertenece al usuario y no expiró."""
        return (
            self.reset_token == token 
            and self.reset_expira 
            and self.reset_expira > datetime.utcnow()
        )


    # --------------------------- Helpers
    def marcar_login(self):
        self.last_login = datetime.utcnow()
        db.session.commit()

    def to_dict(self):
        return {
            "id": self.id,
            "nombre": self.nombre,
            "correo": self.correo,
            "cedula": self.cedula,
            "rol": self.rol.nombre if self.rol else None,
            "activo": self.is_active,
            "ultimo_login": str(self.last_login)
        }

    def __repr__(self):
        return f"<Usuario {self.id} | {self.correo} | rol={self.rol.nombre}>"
