"""
Módulo: asistencias.py
----------------------
Este archivo define el modelo `Asistencia`, que registra la asistencia de un
cliente a una actividad o sesión.

Características principales:
- Relación obligatoria con `Cliente` (cada asistencia pertenece a un cliente).
- Restricción de unicidad: evita duplicar asistencias para el mismo cliente en
la misma fecha.
- Validaciones de integridad para `fecha` y `cliente_id`.
- Serialización a `dict` para exportar datos en formato JSON‑friendly.
"""
from datetime import datetime
from typing import Dict
from sqlalchemy.orm import validates
from extensions import db


class Asistencia(db.Model):
    __tablename__ = "asistencias"

    # ------------- ID -------------
    id: int = db.Column(db.Integer, primary_key=True)

    # ------------- Fecha -------------
    fecha: datetime = db.Column(
        db.DateTime(timezone=True),    
        default=db.func.now(),
        nullable=False,
        index=True,
    )

    # ------------- Cliente -------------
    cliente_id: int = db.Column(
        db.Integer,
        db.ForeignKey("clientes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    cliente = db.relationship(
        "Cliente",
        back_populates="asistencias",
        lazy="select",
    )

    # ------------- Restricciones de integridad -------------
    __table_args__ = (
        db.UniqueConstraint("cliente_id", "fecha", name="uq_cliente_fecha"),
    )

    # ----------------- Validaciones ----------------- #
    @validates("fecha")
    def _validate_fecha(self, key: str, value: datetime) -> datetime:
        if value is None:
            raise ValueError("fecha no puede ser nula.")
        return value

    @validates("cliente_id")
    def _validate_cliente_id(self, key: str, value: int) -> int:
        if value is None:
            raise ValueError("cliente_id no puede ser nulo.")
        return value

    # ----------------- Serialización ----------------- #
    def to_dict(self, include_relations: bool = False) -> Dict:
        data = {
            "id": self.id,
            "fecha": self.fecha.isoformat() if self.fecha else None,
            "cliente_id": self.cliente_id,
        }
        if include_relations:
            data["cliente"] = self.cliente.id if self.cliente else None
        return data

    # ----------------- Representación ----------------- #
    def __repr__(self) -> str:
        fecha = self.fecha.strftime("%d/%m/%Y") if self.fecha else "N/A"
        return f"<Asistencia {self.id} cl={self.cliente_id} f={fecha}>"