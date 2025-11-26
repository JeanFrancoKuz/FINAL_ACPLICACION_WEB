from datetime import datetime
from typing import Optional
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import validates
from extensions import db


class Usuario(UserMixin, db.Model):
    """
    Modelo que representa a un usuario de la aplicación.
    * Se valida email y número de cédula (longitud y formato).
    * Se ofrece `set_password` y `check_password` – protección de password.
    * Relaciones: rol, cliente (una‑a‑una), fotos (una‑a‑varias).
    """

    __tablename__ = "usuarios"
    __table_args__ = (
        db.UniqueConstraint("correo", name="uq_usuario_correo"),
        db.UniqueConstraint("cedula", name="uq_usuario_cedula"),
        db.Index("ix_usuario_rol_id", "rol_id"),
    )

    # --------------------
    # Columnas
    # --------------------
    id: int = db.Column(db.Integer, primary_key=True)
    nombre: str = db.Column(db.String(100), nullable=False)
    correo: str = db.Column(db.String(120), nullable=False, index=True)
    cedula: str = db.Column(db.String(20), nullable=False, index=True)
    password_hash: str = db.Column(db.String(128), nullable=False)
    is_active: bool = db.Column(db.Boolean, default=True, nullable=False)
    last_login: Optional[datetime] = db.Column(
        db.DateTime, default=None, index=True
    )

    # Relación con el rol
    rol_id: int = db.Column(
        db.Integer, db.ForeignKey("roles.id"), nullable=False, index=True
    )
    rol = db.relationship("Rol", back_populates="usuarios")

    # Cliente a uno‑a‑uno (opcional)
    cliente = db.relationship(
        "Cliente", back_populates="usuario", uselist=False
    )

    # Fotos: 1 a ∞, eliminación en cascada
    fotos = db.relationship(
        "Foto",
        back_populates="usuario",
        cascade="all, delete-orphan",
        lazy="select",  # estrategia estándar
    )

    # --------------------
    # Validaciones
    # --------------------
    @validates("correo")
    def validate_correo(self, key: str, address: str) -> str:
        """Valida que el email sea sintácticamente correcto."""
        if not address:
            raise ValueError("El correo no puede estar vacío.")
        if "@" not in address or "." not in address:
            raise ValueError(f"Dirección de correo inválida: {address}")
        return address.lower()

    @validates("cedula")
    def validate_cedula(self, key: str, dato: str) -> str:
        """Valida que el número de cédula sea razonable."""
        if not dato:
            raise ValueError("La cédula no puede estar vacía.")
        # Puedes adaptar la lógica según la normativa de tu país.
        if not dato.isdigit():
            raise ValueError("La cédula sólo debe contener dígitos.")
        if len(dato) > 20:
            raise ValueError("La cédula excede los 20 caracteres.")
        return dato

    # --------------------
    # Seguridad
    # --------------------
    def set_password(self, password: str) -> None:
        """Crea y almacena la hash de la contraseña."""
        if not password:
            raise ValueError("La contraseña no puede estar vacía.")
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verifica la contraseña introducida."""
        return check_password_hash(self.password_hash, password)

    @property
    def password(self):
        """Evita que alguien intente leer la contraseña."""
        raise AttributeError("La contraseña es de sólo escritura. Use `.check_password()`.")

    # --------------------
    # Representación / debugging
    # --------------------
    def __repr__(self) -> str:
        return f"<Usuario {self.id} {self.nombre} ({self.correo})>"
