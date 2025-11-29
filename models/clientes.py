from __future__ import annotations
from datetime import datetime, timedelta
import re
from enum import Enum
from typing import Dict, List, Optional
from extensions import db
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from sqlalchemy import event

# Importaciones para relaciones cruzadas
from models.usuarios import Usuario
from models.pagos import Pago
from models.asistencias import Asistencia
from models.progreso_cliente import ProgresoCliente
from models.fotos import Foto


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
    correo: Mapped[Optional[str]] = mapped_column(db.String(120), unique=True)
    telefono: Mapped[Optional[str]] = mapped_column(db.String(20))
    foto_perfil: Mapped[Optional[str]] = mapped_column(db.String(255))

    # ---------- Estado / membresía ----------
    estado_membresia: Mapped[EstadoMembresia] = mapped_column(
        db.Enum(EstadoMembresia, name="estado_membresia_enum"),
        default=EstadoMembresia.PENDIENTE,
        nullable=False, index=True
    )

    fecha_ingreso: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), default=db.func.now())
    membresia_vencimiento: Mapped[Optional[datetime]] = mapped_column(db.DateTime(timezone=True), index=True)

    # ---------- Relación con usuario (1:1) ----------
    usuario_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("usuarios.id", ondelete="CASCADE"), unique=True)
    usuario: Mapped[Usuario] = relationship("Usuario", back_populates="cliente", uselist=False)

    # ---------- Otras relaciones ----------
    pagos: Mapped[List[Pago]] = relationship("Pago", back_populates="cliente", cascade="all, delete-orphan")
    asistencias: Mapped[List[Asistencia]] = relationship("Asistencia", back_populates="cliente", cascade="all, delete-orphan")
    progresos: Mapped[List[ProgresoCliente]] = relationship("ProgresoCliente", back_populates="cliente", cascade="all, delete-orphan")
    fotos: Mapped[List[Foto]] = relationship("Foto", back_populates="cliente", cascade="all, delete-orphan", lazy="select")


    # ───────────────────────── VALIDACIONES ───────────────────────── #
    @validates("nombre")
    def _validate_nombre(self, key, value):
        if not value or len(value.strip()) < 3:
            raise ValueError("El nombre debe tener mínimo 3 caracteres.")
        return value.strip()

    @validates("telefono")
    def _validate_telefono(self, key, value):
        if value and not re.fullmatch(r"^\+?\d{5,20}$", value):
            raise ValueError("Teléfono inválido. Debe tener entre 5 y 20 dígitos")
        return value

    @validates("correo")
    def _validate_correo(self, key, value):
        if value and ("@" not in value or "." not in value):
            raise ValueError("Correo electrónico inválido")
        return value.lower() if value else None


    # ───────────────────────── MÉTODOS DE NEGOCIO ───────────────────────── #
    def activar_membresia(self, duracion_dias: int = 30):
        self.estado_membresia = EstadoMembresia.ACTIVO
        self.fecha_ingreso = datetime.utcnow()
        self.membresia_vencimiento = self.fecha_ingreso + timedelta(days=duracion_dias)

    def dias_restantes(self) -> Optional[int]:
        if not self.membresia_vencimiento:
            return None
        return max((self.membresia_vencimiento - datetime.utcnow()).days, 0)

    def membresia_activa(self) -> bool:
        return self.estado_membresia == EstadoMembresia.ACTIVO and self.dias_restantes() > 0


    # ───────────────────────── SERIALIZACIÓN ───────────────────────── #
    def to_dict(self, include_relations: bool = False) -> Dict:
        data = {
            "id": self.id,
            "nombre": self.nombre,
            "cedula": self.cedula,
            "correo": self.correo,
            "telefono": self.telefono,
            "foto_perfil": self.foto_perfil,
            "estado_membresia": self.estado_membresia.value,
            "fecha_ingreso": self.fecha_ingreso.isoformat(),
            "membresia_vencimiento": self.membresia_vencimiento.isoformat() if self.membresia_vencimiento else None,
            "dias_restantes": self.dias_restantes(),
            "membresia_activa": self.membresia_activa(),
        }
        if include_relations:
            data["pagos"] = [p.to_dict() for p in self.pagos]
        return data


    # ───────────────────────── REPR ───────────────────────── #
    def __repr__(self):
        venc = self.membresia_vencimiento.strftime("%Y-%m-%d") if self.membresia_vencimiento else "N/A"
        return f"<Cliente {self.nombre} | {self.estado_membresia.value} | vence {venc}>"


# ───────────────────────── EVENTO DE BLOQUEO ───────────────────────── #
@event.listens_for(Cliente, "before_delete")
def _prevent_delete_if_payments(mapper, connection, target: Cliente):
    if target.pagos:
        raise ValueError(f"No se puede eliminar el cliente {target.id}: tiene {len(target.pagos)} pagos.")
