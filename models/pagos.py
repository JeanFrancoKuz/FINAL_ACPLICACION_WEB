from datetime import datetime
from enum import Enum
from typing import Optional, List, TYPE_CHECKING
from extensions import db
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

if TYPE_CHECKING:
    from .clientes import Cliente
    from .fotos import Foto


# ───────────────────────── ENUMS ───────────────────────── #
class EstadoPago(Enum):
    PENDIENTE = "PENDIENTE"
    VALIDADO = "VALIDADO"
    RECHAZADO = "RECHAZADO"


class TipoPago(Enum):
    MENSUALIDAD = "MENSUALIDAD"
    INSCRIPCION = "INSCRIPCION"
    EFECTIVO = "EFECTIVO"
    TRANSFERENCIA = "TRANSFERENCIA/PAGO_MOVIL"
    TARJETA = "TARJETA"


# ───────────────────────── MODELO ───────────────────────── #
class Pago(db.Model):
    __tablename__ = "pagos"

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(
        db.ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    monto: Mapped[float] = mapped_column(nullable=False)
    tipo: Mapped[TipoPago] = mapped_column(
        db.Enum(TipoPago, name="tipo_pago_enum"), nullable=False
    )
    fecha_pago: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), default=db.func.now(), index=True
    )
    observacion: Mapped[Optional[str]] = mapped_column(db.String(255))
    estado: Mapped[EstadoPago] = mapped_column(
        db.Enum(EstadoPago, name="estado_pago_enum"),
        default=EstadoPago.PENDIENTE,
        nullable=False,
        index=True,
    )

    # Relaciones
    cliente: Mapped["Cliente"] = relationship("Cliente", back_populates="pagos")
    fotos: Mapped[List["Foto"]] = relationship(
        "Foto", back_populates="pago", cascade="all, delete-orphan"
    )

    # ───────────────────────── VALIDACIONES ───────────────────────── #
    @validates("monto")
    def validar_monto(self, key, value):
        if value <= 0:
            raise ValueError("El monto del pago debe ser mayor a 0.")
        return value

    # ───────────────────────── BUSINESS LOGIC ───────────────────────── #
    def validar(self):
        """Aprueba el pago (la membresía se maneja en las rutas, no aquí)."""
        self.estado = EstadoPago.VALIDADO

    def rechazar(self):
        """Rechaza el pago."""
        self.estado = EstadoPago.RECHAZADO

    # ───────────────────────── SERIALIZACIÓN ───────────────────────── #
    def to_dict(self, include_fotos: bool = False) -> dict:
        data = {
            "id": self.id,
            "cliente_id": self.cliente_id,
            "monto": self.monto,
            "tipo": self.tipo.value,
            "fecha_pago": self.fecha_pago.isoformat(),
            "observacion": self.observacion,
            "estado": self.estado.value,
        }
        if include_fotos:
            data["fotos"] = [f.to_dict() for f in self.fotos]
        return data

    def __repr__(self):
        return f"<Pago {self.id} Cliente={self.cliente_id} {self.monto} {self.estado.value}>"
