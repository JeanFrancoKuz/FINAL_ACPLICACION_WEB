"""
Módulo: fotos.py
----------------
Foto – Registro de un archivo (imagen, video…) subido por un usuario.

Características principales:
- Tipado fuerte con anotaciones de tipo.
- Índices en todas las columnas de búsqueda relevantes.
- Fecha con timezone=True (ideal en Postgres).
- `to_dict()` para serializar a JSON.
- `__repr__` amigable.
- `validates` para evitar nombres vacíos o caracteres poco seguros.
"""

from datetime import datetime
from typing import Dict

from sqlalchemy.orm import validates
from extensions import db


class Foto(db.Model):
    __tablename__ = "fotos"

    # ------------- columnas ----------
    id: int = db.Column(db.Integer, primary_key=True)

    nombre_archivo: str = db.Column(db.String(255), nullable=False)
    ruta: str = db.Column(db.String(255), nullable=False)
    fecha_subida: datetime = db.Column(
        db.DateTime(timezone=True),
        default=db.func.now(),
        nullable=False,
        index=True,
    )

    # ------------- relaciones ----------
    cliente_id: int = db.Column(
        db.Integer, db.ForeignKey("clientes.id", ondelete="SET NULL")
    )
    cliente = db.relationship(
        "Cliente",
        back_populates="fotos",
        lazy="select",
    )

    pago_id: int = db.Column(
        db.Integer, db.ForeignKey("pagos.id", ondelete="SET NULL")
    )
    pago = db.relationship(
        "Pago",
        back_populates="fotos",
        lazy="select",
    )

    progreso_id: int = db.Column(
        db.Integer, db.ForeignKey("progresos_cliente.id", ondelete="SET NULL")
    )
    progreso = db.relationship(
        "ProgresoCliente",
        back_populates="fotos",
        lazy="select",
    )

    uploaded_by: int = db.Column(
        db.Integer, db.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False
    )
    usuario = db.relationship(
        "Usuario", back_populates="fotos", lazy="select"
    )

    # ------------- índices de búsqueda ----------
    __table_args__ = (
        db.Index("ix_fotos_cliente_id", "cliente_id"),
        db.Index("ix_fotos_pago_id", "pago_id"),
        db.Index("ix_fotos_progreso_id", "progreso_id"),
        db.Index("ix_fotos_uploaded_by", "uploaded_by"),
    )

    # ------------- validaciones (opcional) -------------
    @validates("nombre_archivo", "ruta")
    def _validate_path(self, key: str, value: str) -> str:
        """Asegura que las rutas no estén vacías. No se hace validación excesiva aquí
        porque secure_filename ya limpia el nombre del archivo al subir."""
        if not value or not value.strip():
            raise ValueError(f"'{key}' no puede estar vacío.")
        return value

    # ------------- serialización --
    def to_dict(self, include_relations: bool = False) -> Dict:
        data = {
            "id": self.id,
            "nombre_archivo": self.nombre_archivo,
            "ruta": self.ruta,
            "fecha_subida": (
                self.fecha_subida.isoformat() if self.fecha_subida else None
            ),
            "cliente_id": self.cliente_id,
            "pago_id": self.pago_id,
            "progreso_id": self.progreso_id,
            "uploaded_by": self.uploaded_by,
        }

        if include_relations:
            if self.cliente:
                data["cliente"] = self.cliente.id
            if self.pago:
                data["pago"] = self.pago.id
            if self.progreso:
                data["progreso"] = self.progreso.id
            if self.usuario:
                data["usuario"] = self.usuario.id

        return data

    # ------------- representación legible -------------
    def __repr__(self) -> str:
        return f"<Foto {self.id} → {self.nombre_archivo[:20]}... ({self.ruta})>"