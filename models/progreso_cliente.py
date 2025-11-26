
from datetime import datetime
from typing import Dict, Optional

from sqlalchemy.orm import validates
from extensions import db

# ------------------------------------------------------------------
# Modelo: Progreso de un cliente (peso, altura, etc.)
# ------------------------------------------------------------------
class ProgresoCliente(db.Model):
    """Registro de estado físico de un cliente."""

    __tablename__ = "progresos_cliente"

    # ---------- Columnas ----------
    id: int = db.Column(db.Integer, primary_key=True)
    cliente_id: int = db.Column(
        db.Integer,
        db.ForeignKey("clientes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fecha_registro: datetime = db.Column(
        db.DateTime(timezone=True), default=db.func.now(), nullable=False, index=True
    )
    peso: float = db.Column(db.Float, nullable=False)          # kg
    altura: float = db.Column(db.Float, nullable=False)        # m
    grasa_corporal: Optional[float] = db.Column(db.Float)     # %
    masa_muscular: Optional[float] = db.Column(db.Float)     # %

    # ---------- Relaciones ----------
    cliente = db.relationship("Cliente", back_populates="progresos")

    fotos = db.relationship(
        "Foto",
        back_populates="progreso",
        cascade="all, delete-orphan",
        lazy="select",
    )

    # ------------------------------------------------------------------
    # Validaciones automáticas (opcional)
    # ------------------------------------------------------------------
    @validates("peso", "altura", "grasa_corporal", "masa_muscular")
    def _validate_metrica(self, key: str, value: Optional[float]) -> Optional[float]:
        """
        - `peso` y `altura` deben > 0
        - `grasa_corporal` y `masa_muscular` (si existen) entre 0 y 100
        """
        if key in ("peso", "altura"):
            if value is None or value <= 0:
                raise ValueError(f"{key} debe ser mayor a 0.")
            return value

        if value is not None:
            if not 0 <= value <= 100:
                raise ValueError(f"{key} debe estar entre 0 y 100.")
        return value  # para `None`

    # ------------------------------------------------------------------
    # +⬇Serialización  (método opcional)
    # ------------------------------------------------------------------
    def to_dict(self, include_fotos: bool = False) -> Dict:
        data = {
            "id": self.id,
            "cliente_id": self.cliente_id,
            "fecha_registro": (
                self.fecha_registro.isoformat() if self.fecha_registro else None
            ),
            "peso": self.peso,
            "altura": self.altura,
            "grasa_corporal": self.grasa_corporal,
            "masa_muscular": self.masa_muscular,
        }
        if include_fotos:
            data["fotos"] = [f.to_dict() for f in self.fotos]
        return data

    # ------------------------------------------------------------------
    # +Representación legible
    # ------------------------------------------------------------------
    def __repr__(self) -> str:
        fecha = (
            self.fecha_registro.strftime("%Y-%m-%d")
            if self.fecha_registro
            else "inicial"
        )
        return f"<ProgresoCliente {self.id} (c={self.cliente_id}) {fecha}>"
