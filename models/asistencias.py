"""
Modelo: Asistencia
------------------
Registro de acceso del cliente al gimnasio.

Características:
✔ Evita asistencia duplicada el mismo día por cliente
✔ Validación estricta de datos
✔ Utilidades para reportes mensuales
✔ Serialización lista para APIs
✔ Modelo simple, escalable y robusto
"""

from datetime import datetime, date
from typing import Dict, Optional
from sqlalchemy.orm import validates, Mapped, mapped_column, relationship
from sqlalchemy import func
from extensions import db


class Asistencia(db.Model):
    __tablename__ = "asistencias"

    # =======================================================
    # 📌 DATOS PRINCIPALES
    # =======================================================
    id: Mapped[int] = mapped_column(primary_key=True)

    fecha: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        default=db.func.now(),
        nullable=False,
        index=True
    )

    # =======================================================
    # 📌 RELACIÓN CON CLIENTE
    # =======================================================
    cliente_id: Mapped[int] = mapped_column(
        db.Integer,
        db.ForeignKey("clientes.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    cliente = relationship("Cliente", back_populates="asistencias", lazy="select")

    # =======================================================
    # 📌 DATOS OPCIONALES (Útiles en reportes)
    # =======================================================
    tipo: Mapped[Optional[str]] = mapped_column(
        db.String(50),
        default="ENTRENAMIENTO",
        index=True
    )

    observacion: Mapped[Optional[str]] = mapped_column(
        db.String(255),
        nullable=True
    )

    # =======================================================
    # 🚫 RESTRICCIÓN ANTI-DUPLICADO
    # =======================================================
    __table_args__ = (
        db.UniqueConstraint(
            "cliente_id",
            "fecha",
            name="uq_asistencia_cliente_fecha"
        ),
    )

    # =======================================================
    # ✔ VALIDACIONES
    # =======================================================
    @validates("fecha")
    def validar_fecha(self, _, value):
        if not value:
            raise ValueError("La fecha de asistencia no puede estar vacía.")
        return value

    @validates("cliente_id")
    def validar_cliente(self, _, value):
        if not value:
            raise ValueError("Debe especificarse un cliente.")
        return value

    @validates("tipo")
    def validar_tipo(self, _, value):
        tipos_validos = {
            "ENTRENAMIENTO",
            "PESAS",
            "CARDIO",
            "CLASE"
        }
        return value if value in tipos_validos else "ENTRENAMIENTO"

    # =======================================================
    # ⚙ MÉTODOS DE NEGOCIO
    # =======================================================

    @classmethod
    def registrar(cls, cliente_id: int, tipo: str = "ENTRENAMIENTO", observ: str = None):
        """
        Registra asistencia si no existe otra hoy.
        Devuelve la asistencia existente si ya estaba registrada.
        """
        hoy = date.today()

        existente = cls.query.filter(
            func.date(cls.fecha) == hoy,
            cls.cliente_id == cliente_id
        ).first()

        if existente:
            return existente  # No revienta la app 👍

        nueva = cls(
            cliente_id=cliente_id,
            tipo=tipo,
            observacion=observ
        )

        db.session.add(nueva)
        db.session.commit()
        return nueva


    @classmethod
    def asistencias_mes(cls, cliente_id: int, mes: int, anio: int) -> int:
        """Cantidad total de asistencias en un mes y año."""
        return cls.query.filter(
            cls.cliente_id == cliente_id,
            func.extract("month", cls.fecha) == mes,
            func.extract("year", cls.fecha) == anio
        ).count()


    @classmethod
    def ultima_asistencia(cls, cliente_id: int):
        """Devuelve la última fecha de asistencia del cliente."""
        return cls.query.filter_by(cliente_id=cliente_id).order_by(cls.fecha.desc()).first()


    # =======================================================
    # 🧾 SERIALIZACIÓN
    # =======================================================

    def to_dict(self, include_cliente: bool = False) -> Dict:
        data = {
            "id": self.id,
            "fecha": self.fecha.isoformat(),
            "cliente_id": self.cliente_id,
            "tipo": self.tipo,
            "observacion": self.observacion
        }
        if include_cliente and self.cliente:
            data["cliente"] = {
                "id": self.cliente.id,
                "nombre": self.cliente.nombre
            }
        return data

    # =======================================================
    # 🧿 REPRESENTACIÓN
    # =======================================================

    def __repr__(self):
        fecha = self.fecha.astimezone().strftime("%d/%m/%Y %H:%M")
        return f"<Asistencia Cliente={self.cliente_id} | {fecha} | {self.tipo}>"
