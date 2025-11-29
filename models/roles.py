from __future__ import annotations
from typing import List
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from models.usuarios import Usuario
from extensions import db

class Rol(db.Model):
    __tablename__ = "roles"
    __table_args__ = (db.UniqueConstraint("nombre", name="uq_rol_nombre"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(db.String(50), nullable=False, unique=True)
    descripcion: Mapped[str] = mapped_column(db.String(200), nullable=True)  # opcional

    usuarios: Mapped[List["Usuario"]] = relationship(
        "Usuario", back_populates="rol",
        cascade="all, delete-orphan", lazy="select"
    )

    @validates("nombre")
    def validar(self, key, value):
        if not value or not value.strip():
            raise ValueError("El nombre del rol no puede estar vacío.")
        return value.strip()

    def es(self, nombre: str) -> bool:
        """Permite validar acceso fácilmente"""
        return self.nombre.upper() == nombre.upper()

    def __repr__(self):
        return f"<Rol {self.id} - {self.nombre}>"
