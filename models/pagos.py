from datetime import datetime
from enum import Enum
from typing import Optional, List
from extensions import db

from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .clientes import Cliente
    from .fotos import Foto

# ------------------------------------------------------------------
# Enumeraciones
# ------------------------------------------------------------------
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


# ------------------------------------------------------------------
# Modelo Pago
# ------------------------------------------------------------------
class Pago(db.Model):
    """Registro de un pago (mensualidad, inscripción, etc.)."""
    __tablename__ = "pagos"

    # ------------- Columnas -------------
    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(
        db.ForeignKey("clientes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    monto: Mapped[float] = mapped_column(nullable=False)
    tipo: Mapped[TipoPago] = mapped_column(
        db.Enum(TipoPago, name="tipo_pago_enum", native_enum=False),
        nullable=False,
    )
    fecha_pago: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        default=db.func.now(),
        index=True,
        nullable=False,
    )
    observacion: Mapped[Optional[str]] = mapped_column(db.String(255))
    estado: Mapped[EstadoPago] = mapped_column(
        db.Enum(EstadoPago, name="estado_pago_enum", native_enum=False),
        nullable=False,
        default=EstadoPago.PENDIENTE,
        index=True,
    )

    # ------------- Relaciones -------------
    cliente: Mapped["Cliente"] = relationship("Cliente", back_populates="pagos")
    fotos: Mapped[List["Foto"]] = relationship(
        "Foto",
        back_populates="pago",
        cascade="all, delete-orphan",
        lazy="select",
    )

    # ------------------------------------------------------------------
    # Métodos de negocio
    # ------------------------------------------------------------------
    def validar(self) -> None:
        """Aprueba el pago."""
        self.estado = EstadoPago.VALIDADO

    def rechazar(self) -> None:
        """Rechaza el pago."""
        self.estado = EstadoPago.RECHAZADO

    # ------------------------------------------------------------------
    # Validaciones adicionales
    # ------------------------------------------------------------------
    def validar_monto(self) -> None:
        """Valida que el monto sea mayor a 0."""
        if self.monto <= 0:
            raise ValueError("El monto del pago debe ser mayor a 0.")

    # ------------------------------------------------------------------
    # Serialización auxiliar
    # ------------------------------------------------------------------
    def to_dict(self, include_fotos: bool = False) -> dict:
        """Convierte a dict (útil para JSON)."""
        data = {
            "id": self.id,
            "cliente_id": self.cliente_id,
            "monto": self.monto,
            "tipo": self.tipo.value,
            "fecha_pago": self.fecha_pago.isoformat() if self.fecha_pago else None,
            "observacion": self.observacion,
            "estado": self.estado.value,
        }
        if include_fotos:
            data["fotos"] = [f.to_dict() for f in self.fotos]
        return data

    # ------------------------------------------------------------------
    # Representación legible
    # ------------------------------------------------------------------
    def __repr__(self) -> str:
        return (
            f"<Pago {self.id} | cliente={self.cliente_id} "
            f"| {self.monto} | {self.estado.value}>"
        )