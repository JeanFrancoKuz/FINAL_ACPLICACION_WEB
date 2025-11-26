"""
Modelo de roles de la aplicación.  
La relación `usuarios` se describe con ``List[Usuario]`` y se declara
solo para el análisis de tipos (``TYPE_CHECKING``) para evitar
circular imports en tiempo de ejecución.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List
from sqlalchemy.orm import validates
from extensions import db

# Importa la clase solo si el IDE o el tipo‑checker lo necesita
if TYPE_CHECKING:            # pragma: no cover
    from .usuarios import Usuario

class Rol(db.Model):
    __tablename__ = "roles"
    __table_args__ = (
        db.UniqueConstraint("nombre", name="uq_rol_nombre"),
    )

    # ------------------------------------------------------------------ #
    # Columnas
    # ------------------------------------------------------------------ #
    id: int = db.Column(db.Integer, primary_key=True)
    nombre: str = db.Column(
        db.String(50), nullable=False, unique=True
    )

    # ------------------------------------------------------------------ #
    # Relación bidireccional con Usuario
    # ------------------------------------------------------------------ #
    usuarios: List[Usuario] = db.relationship(
        "Usuario",
        back_populates="rol",
        cascade="all, delete-orphan",
        lazy="select",
    )

    # ------------------------------------------------------------------ #
    # Validaciones (run‑time)
    # ------------------------------------------------------------------ #
    @validates("nombre")
    def _validate_nombre(self, key: str, value: str) -> str:
        """Evita nombres vacíos o demasiado largos."""
        if not value or not value.strip():
            raise ValueError("El nombre del rol no puede estar vacío.")
        if len(value) > 50:
            raise ValueError("El nombre del rol no puede superar los 50 caracteres.")
        return value.strip()

    # ------------------------------------------------------------------ #
    # Representación de depuración
    # ------------------------------------------------------------------ #
    def __repr__(self) -> str:   # pragma: no cover
        return f"<Rol {self.id}: {self.nombre}>"
