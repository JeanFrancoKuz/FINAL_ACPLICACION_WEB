"""
Módulo: fotos.py
----------------
Foto – Archivo subido por cliente o administrador.

Incluye:
✔ control de integridad
✔ relaciones con Cliente / Pago / Progreso / Usuario
✔ serialización completa
✔ validación de nombres y rutas
"""

from datetime import datetime
from typing import Dict
import os

from sqlalchemy.orm import validates, Mapped, mapped_column, relationship
from extensions import db


# ───────────────────────── MODELO FOTO ───────────────────────── #
class Foto(db.Model):
    __tablename__ = "fotos"

    # ---------- Datos básicos ----------
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre_archivo: Mapped[str] = mapped_column(db.String(255), nullable=False)
    ruta: Mapped[str] = mapped_column(db.String(255), nullable=False)
    fecha_subida: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), default=db.func.now(), index=True
    )

    # ---------- Relaciones ----------
    cliente_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("clientes.id", ondelete="SET NULL"))
    cliente = relationship("Cliente", back_populates="fotos", lazy="select")

    pago_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("pagos.id", ondelete="SET NULL"))
    pago = relationship("Pago", back_populates="fotos", lazy="select")

    progreso_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("progresos_cliente.id", ondelete="SET NULL"))
    progreso = relationship("ProgresoCliente", back_populates="fotos", lazy="select")

    uploaded_by: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("usuarios.id", ondelete="CASCADE"))
    usuario = relationship("Usuario", back_populates="fotos", lazy="select")

    # ---------- Índices recomendados ----------
    __table_args__ = (
        db.Index("ix_fotos_cliente_id", "cliente_id"),
        db.Index("ix_fotos_pago_id", "pago_id"),
        db.Index("ix_fotos_progreso_id", "progreso_id"),
        db.Index("ix_fotos_uploaded_by", "uploaded_by"),
        db.Index("ix_foto_nombre_archivo", "nombre_archivo"),
    )


    # ───────────────────────── VALIDACIONES ───────────────────────── #
    @validates("nombre_archivo")
    def validar_nombre(self, key, value):
        if not value.strip():
            raise ValueError("El nombre del archivo no puede estar vacío.")

        # Validar extensiones
        ext = os.path.splitext(value)[1].lower()
        extensiones_permitidas = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
        if ext not in extensiones_permitidas:
            raise ValueError(f"Extensión de archivo no permitida: {ext}")

        return value

    @validates("ruta")
    def validar_ruta(self, key, value):
        if not value.strip():
            raise ValueError("La ruta no puede ser vacía")
        return value


    # ───────────────────────── SERIALIZACIÓN JSON ───────────────────────── #
    def to_dict(self, include_relations: bool = False) -> Dict:
        data = {
            "id": self.id,
            "nombre_archivo": self.nombre_archivo,
            "ruta": self.ruta,
            "fecha_subida": self.fecha_subida.isoformat(),
            "cliente_id": self.cliente_id,
            "pago_id": self.pago_id,
            "progreso_id": self.progreso_id,
            "uploaded_by": self.uploaded_by,
        }

        if include_relations:
            data["cliente"] = self.cliente.to_dict() if self.cliente else None
            data["pago"] = self.pago.to_dict() if self.pago else None
            data["progreso"] = self.progreso.to_dict() if self.progreso else None
            data["usuario"] = self.usuario.to_dict() if self.usuario else None

        return data


    # ───────────────────────── REPRESENTACIÓN ───────────────────────── #
    def __repr__(self):
        return f"<Foto {self.id} {self.nombre_archivo} ({self.ruta})>"
