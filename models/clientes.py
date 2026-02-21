from __future__ import annotations
from datetime import datetime, timedelta
import re
from enum import Enum
from typing import Dict, List, Optional
from extensions import db
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from models.usuarios import Usuario
from models.pagos import Pago
from models.asistencias import Asistencia
from models.progreso_cliente import ProgresoCliente
from models.fotos import Foto
from sqlalchemy import event

# ────────────────────────── ENUM ────────────────────────── #
class EstadoMembresia(Enum):
    ACTIVO = "ACTIVO"
    INACTIVO = "INACTIVO"
    PENDIENTE = "PENDIENTE"
    SUSPENDIDO = "SUSPENDIDO"
    VENCIDO = "VENCIDO"

# ────────────────────────── MODELO ────────────────────────── #
class Cliente(db.Model):
    __tablename__ = "clientes"

    # ---------- Datos básicos ----------
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(db.String(100), nullable=False)
    cedula: Mapped[str] = mapped_column(db.String(20), unique=True, nullable=False)
    correo: Mapped[Optional[str]] = mapped_column(db.String(120), unique=True, nullable=True)
    telefono: Mapped[Optional[str]] = mapped_column(db.String(20), nullable=True)
    foto_perfil: Mapped[Optional[str]] = mapped_column(db.String(255), nullable=True)

    # ---------- Estado de membresía ----------
    estado_membresia: Mapped[EstadoMembresia] = mapped_column(
        db.Enum(EstadoMembresia, name="estado_membresia_enum"),
        default=EstadoMembresia.PENDIENTE,
        nullable=False,
        index=True,
    )

    # ---------- Fechas ----------
    fecha_ingreso: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), default=db.func.now(), nullable=False)
    membresia_vencimiento: Mapped[Optional[datetime]] = mapped_column(db.DateTime(timezone=True), index=True, nullable=True)

    # ---------- Relación 1‑a‑1 con Usuario ----------
    usuario_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, unique=True)
    usuario: Mapped["Usuario"] = relationship("Usuario", back_populates="cliente", uselist=False)

    # ---------- Otras relaciones ----------
    pagos: Mapped[List["Pago"]] = relationship("Pago", back_populates="cliente", cascade="all, delete-orphan")
    asistencias: Mapped[List["Asistencia"]] = relationship("Asistencia", back_populates="cliente", cascade="all, delete-orphan")
    progresos: Mapped[List["ProgresoCliente"]] = relationship("ProgresoCliente", back_populates="cliente", cascade="all, delete-orphan")
    fotos: Mapped[List["Foto"]] = relationship("Foto", back_populates="cliente", cascade="all, delete-orphan", lazy="select")

    # ───────────────────────── VALIDACIONES ───────────────────────── #
    @validates("telefono")
    def _validate_telefono(self, key: str, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if not re.fullmatch(r"^\+?\d{5,20}$", value):
            raise ValueError("El teléfono debe contener entre 5 y 20 dígitos y puede comenzar con ‘+’.")
        return value

    @validates("correo")
    def _validate_correo(self, key: str, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if "@" not in value or "." not in value:
            raise ValueError("Dirección de correo inválida.")
        return value.lower()

    # ───────────────────────── MÉTODOS DE NEGOCIO ───────────────────────── #
    def activar_membresia(self, duracion_dias: int = 30) -> None:
        self.estado_membresia = EstadoMembresia.ACTIVO
        self.fecha_ingreso = datetime.utcnow()
        self.membresia_vencimiento = self.fecha_ingreso + timedelta(days=duracion_dias)

    def dias_restantes(self) -> Optional[int]:
        if self.membresia_vencimiento is None:
            return None
        delta = self.membresia_vencimiento - datetime.utcnow()
        return delta.days

    def membresia_activa(self) -> bool:
        return (
            self.estado_membresia == EstadoMembresia.ACTIVO
            and self.membresia_vencimiento
            and self.membresia_vencimiento > datetime.utcnow()
        )

    # ───────────────────────── SERIALIZACIÓN ───────────────────────── #
    def to_dict(self, include_relations: bool = False) -> Dict:
        data: Dict = {
            "id": self.id,
            "nombre": self.nombre,
            "cedula": self.cedula,
            "correo": self.correo,
            "telefono": self.telefono,
            "foto_perfil": self.foto_perfil,
            "estado_membresia": self.estado_membresia.value,
            "fecha_ingreso": self.fecha_ingreso.isoformat() if self.fecha_ingreso else None,
            "membresia_vencimiento": self.membresia_vencimiento.isoformat() if self.membresia_vencimiento else None,
            "dias_restantes": self.dias_restantes(),
            "membresia_activa": self.membresia_activa(),
        }
        if include_relations:
            data["pagos"] = [p.to_dict() for p in self.pagos]
        return data

    # ───────────────────────── REPR ───────────────────────── #
    def __repr__(self) -> str:
        venc = self.membresia_vencimiento.strftime("%Y-%m-%d") if self.membresia_vencimiento else "N/A"
        return f"<Cliente {self.id} {self.nombre} ({self.estado_membresia.value}) Vence: {venc}>"

# ───────────────────────── EVENT DE BIRTH ───────────────────────── #
@event.listens_for(Cliente, "before_delete")
def _prevent_delete_if_payments(mapper, connection, target: Cliente) -> None:
    if target.pagos:
        raise ValueError(f"No es posible eliminar el cliente {target.id} – aún tiene {len(target.pagos)} pagos registrados.")
