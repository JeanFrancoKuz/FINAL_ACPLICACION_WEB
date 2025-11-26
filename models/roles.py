from __future__ import annotations
from typing import List
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from models.usuarios import Usuario
from extensions import db

class Rol(db.Model):
    """
    Modelo de roles de la aplicación.
    La relación `usuarios` es bidireccional con Usuario usando Mapped[List["Usuario"]].
    """

    __tablename__ = "roles"
    __table_args__ = (
        db.UniqueConstraint("nombre", name="uq_rol_nombre"),
    )

    # --------------------
    # Columnas
    # --------------------
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(db.String(50), nullable=False, unique=True)

    # --------------------
    # Relación bidireccional con Usuario
    # --------------------
    usuarios: Mapped[List["Usuario"]] = relationship(
        "Usuario",
        back_populates="rol",
        cascade="all, delete-orphan",
        lazy="select",
    )

    # --------------------
    # Validaciones (run-time)
    # --------------------
    @validates("nombre")
    def _validate_nombre(self, key: str, value: str) -> str:
        """Evita nombres vacíos o demasiado largos."""
        if not value or not value.strip():
            raise ValueError("El nombre del rol no puede estar vacío.")
        if len(value) > 50:
            raise ValueError("El nombre del rol no puede superar los 50 caracteres.")
        return value.strip()

    # --------------------
    # Representación de depuración
    # --------------------
    def __repr__(self) -> str:
        return f"<Rol {self.id}: {self.nombre}>"
