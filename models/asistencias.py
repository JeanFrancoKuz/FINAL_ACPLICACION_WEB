"""
Modelo: Asistencia
------------------
Registro de acceso del cliente al gimnasio.

✔ Evita asistencia duplicada en el mismo día
✔ Serialización lista para API/Front
✔ Relación directa con Cliente
✔ Utilidades para reportes mensuales
"""

from datetime import datetime, date
from typing import Dict
from sqlalchemy.orm import validates, Mapped, mapped_column, relationship
from sqlalchemy import func
from extensions import db


class Asistencia(db.Model):
    __tablename__ = "asistencias"

    # ------------------- Datos Base -------------------
    id: Mapped[int] = mapped_column(primary_key=True)
    fecha: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        default=db.func.now(),
        nullable=False,
        index=True
    )

    # ------------------- Relación Cliente -------------------
    cliente_id: Mapped[int] = mapped_column(
        db.Integer, db.ForeignKey("clientes.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    cliente = relationship("Cliente", back_populates="asistencias", lazy="select")

    # ------------------- Restricción Anti-Duplicado -------------------
    __table_args__ = (
        db.UniqueConstraint("cliente_id", "fecha", name="uq_cliente_fecha"),
    )


    # ---------------- VALIDACIONES ---------------- #
    @validates("fecha")
    def validar_fecha(self, _, value):
        if value is None:
            raise ValueError("La fecha de asistencia no puede ser nula.")
        return value

    @validates("cliente_id")
    def validar_cliente(self, _, value):
        if not value:
            raise ValueError("cliente_id es obligatorio.")
        return value


    # ---------------- MÉTODOS DE NEGOCIO ---------------- #
    @classmethod
    def registrar(cls, cliente_id:int) -> "Asistencia":
        """
        Crea asistencia si aún no existe en el día.
        Evita errores por duplicados sin romper la app.
        """
        hoy = date.today()

        existente = cls.query.filter(
            func.date(cls.fecha) == hoy,
            cls.cliente_id == cliente_id
        ).first()

        if existente:
            return existente  # No genera error, devuelve la existente

        nueva = cls(cliente_id=cliente_id)
        db.session.add(nueva)
        db.session.commit()
        return nueva


    @classmethod
    def asistencias_del_mes(cls, cliente_id:int, mes:int, anio:int) -> int:
        """Devuelve el total de asistencias en un mes específico."""
        return cls.query.filter(
            cls.cliente_id == cliente_id,
            func.extract('month', cls.fecha) == mes,
            func.extract('year', cls.fecha) == anio
        ).count()


    # ---------------- SERIALIZACIÓN ---------------- #
    def to_dict(self, include_cliente=False) -> Dict:
        data = {
            "id": self.id,
            "fecha": self.fecha.isoformat(),
            "cliente_id": self.cliente_id
        }
        if include_cliente and self.cliente:
            data["cliente"] = {
                "id": self.cliente.id,
                "nombre": self.cliente.nombre
            }
        return data

    # ---------------- REPRESENTACIÓN ---------------- #
    def __repr__(self):
        fecha = self.fecha.strftime("%d/%m/%Y %H:%M")
        return f"<Asistencia id={self.id} Cliente={self.cliente_id} | {fecha}>"
