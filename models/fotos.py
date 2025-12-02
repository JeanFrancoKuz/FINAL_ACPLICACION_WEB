from datetime import datetime
import os
from typing import Dict

from sqlalchemy.orm import validates, Mapped, mapped_column, relationship
from extensions import db


class Foto(db.Model):
    __tablename__ = "fotos"

    id: Mapped[int] = mapped_column(primary_key=True)

    nombre_archivo: Mapped[str] = mapped_column(db.String(255), nullable=False)
    ruta: Mapped[str] = mapped_column(db.String(255), nullable=False)

    fecha_subida: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        default=db.func.now(),
        index=True
    )

    # =============================
    # 🔗 RELACIONES (CORREGIDO)
    # =============================

    cliente_id: Mapped[int] = mapped_column(
        db.Integer,
        db.ForeignKey("clientes.id", ondelete="SET NULL"),
        nullable=True
    )
    cliente = relationship("Cliente", back_populates="fotos", lazy="select")

    pago_id: Mapped[int] = mapped_column(
        db.Integer,
        db.ForeignKey("pagos.id", ondelete="SET NULL"),
        nullable=True
    )
    pago = relationship("Pago", back_populates="fotos", lazy="select")

    progreso_id: Mapped[int] = mapped_column(
        db.Integer,
        db.ForeignKey("progresos_cliente.id", ondelete="SET NULL"),
        nullable=True         # 👈 ESTO ERA EL ERROR
    )
    progreso = relationship("ProgresoCliente", back_populates="fotos", lazy="select")

    uploaded_by: Mapped[int] = mapped_column(
        db.Integer,
        db.ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False
    )
    usuario = relationship("Usuario", lazy="select")

    __table_args__ = (
        db.Index("ix_fotos_cliente_id", "cliente_id"),
        db.Index("ix_fotos_pago_id", "pago_id"),
        db.Index("ix_fotos_progreso_id", "progreso_id"),
    )

    # =============================
    # ✔ VALIDACIONES
    # =============================

    @validates("nombre_archivo")
    def validar_nombre(self, key, value):
        ext = os.path.splitext(value)[1].lower()
        permitidas = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".pdf"}

        if ext not in permitidas:
            raise ValueError(f"Extensión de archivo no permitida: {ext}")

        return value

    # =============================
    # 🌐 JSON
    # =============================
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "nombre_archivo": self.nombre_archivo,
            "ruta": self.ruta,
            "fecha_subida": self.fecha_subida.isoformat(),
            "cliente_id": self.cliente_id,
            "pago_id": self.pago_id,
            "progreso_id": self.progreso_id,
            "uploaded_by": self.uploaded_by,
        }


    def __repr__(self):
        return f"<Foto {self.id} {self.nombre_archivo}>"
