from datetime import datetime
from typing import Dict, Optional
from sqlalchemy.orm import validates, Mapped, mapped_column, relationship
from extensions import db


class ProgresoCliente(db.Model):
    __tablename__ = "progresos_cliente"

    # ---------- Campos ----------
    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(
        db.Integer, db.ForeignKey("clientes.id", ondelete="CASCADE"), index=True
    )
    fecha_registro: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), default=db.func.now(), index=True
    )

    peso: Mapped[float] = mapped_column(nullable=False)         # kg
    altura: Mapped[float] = mapped_column(nullable=False)       # metros
    grasa_corporal: Mapped[Optional[float]] = mapped_column(db.Float) # %
    masa_muscular: Mapped[Optional[float]] = mapped_column(db.Float) # %

    # ---------- Relaciones ----------
    cliente = relationship("Cliente", back_populates="progresos")
    fotos = relationship(
        "Foto", back_populates="progreso", cascade="all, delete-orphan"
    )

    # ---------- Validaciones ----------
    @validates("peso", "altura", "grasa_corporal", "masa_muscular")
    def validar_metricas(self, key, value):
        if key in ("peso", "altura"):
            if not value or value <= 0:
                raise ValueError(f"{key} debe ser mayor a 0")
        else:
            if value is not None and not 0 <= value <= 100:
                raise ValueError(f"{key} debe estar entre 0 y 100")
        return value

    # ---------- Cálculo automático ----------
    def calcular_imc(self) -> Optional[float]:
        """Retorna IMC/ BMI redondeado a 2 decimales."""
        try:
            return round(self.peso / (self.altura**2), 2)
        except:
            return None

    # ---------- Serialización ----------
    def to_dict(self, include_fotos=False) -> Dict:
        data = {
            "id": self.id,
            "cliente_id": self.cliente_id,
            "fecha_registro": self.fecha_registro.isoformat(),
            "peso": self.peso,
            "altura": self.altura,
            "grasa_corporal": self.grasa_corporal,
            "masa_muscular": self.masa_muscular,
            "imc": self.calcular_imc(),
        }
        if include_fotos:
            data["fotos"] = [f.to_dict() for f in self.fotos]
        return data

    def __repr__(self) -> str:
        return f"<ProgresoCliente {self.id} cliente={self.cliente_id} fecha={self.fecha_registro:%Y-%m-%d}>"
