"""
Modelo Cliente – 1‑a‑1 con Usuario y relaciones a pagos, asistencias,
progreso y fotos.

Versión con:
    • Import correcto de `validates` y `event`.
    • Importes de tipado necesarios (List, Dict, Optional, TYPE_CHECKING).
    • Ajuste de nombres de los archivos de modulo (pagos, asistencias, …).
"""

# ─────────────────────────────── IMPORTS ─────────────────────────────── #
from datetime import datetime, timedelta
import re
from enum import Enum
from typing import Dict, List, Optional, TYPE_CHECKING
# Instancia central de SQLAlchemy (ya está inicializada en extensions.py)
from extensions import db
# Decorador de validación y el mecanismo de eventos
from sqlalchemy.orm import validates
from sqlalchemy import event

# ──────────────────────── TYPE‑CHECKING IMPORTS ──────────────────────── #
if TYPE_CHECKING:                      # pragma: no cover
    from .pagos import Pago
    from .asistencias import Asistencia
    from .progreso_cliente import ProgresoCliente
    from .fotos import Foto


# ────────────────────────── ENUMS ────────────────────────── #
class EstadoMembresia(Enum):
    ACTIVO = "ACTIVO"
    INACTIVO = "INACTIVO"
    PENDIENTE = "PENDIENTE"
    SUSPENDIDO = "SUSPENDIDO"
    VENCIDO = "VENCIDO"


# ────────────────────────────────── MODELO ────────────────────────────────── #
class Cliente(db.Model):
    __tablename__ = "clientes"

    # ---------- Datos básicos ----------
    id: int = db.Column(db.Integer, primary_key=True)
    nombre: str = db.Column(db.String(100), nullable=False)
    cedula: str = db.Column(db.String(20), unique=True, nullable=False)
    correo: str = db.Column(db.String(120), unique=True, nullable=True)
    telefono: str = db.Column(db.String(20), nullable=True)
    foto_perfil = db.Column(db.String(255), nullable=True)

    # ---------- Estado de membresía ----------
    estado_membresia = db.Column(
        db.Enum(EstadoMembresia, name="estado_membresia_enum"),
        default=EstadoMembresia.PENDIENTE,
        nullable=False,
        index=True,  # para filtros frecuentemente
    )

    # ---------- Fechas ----------
    fecha_ingreso = db.Column(
        db.DateTime(timezone=True), default=db.func.now(), nullable=False
    )
    membresia_vencimiento = db.Column(
        db.DateTime(timezone=True), index=True, nullable=True
    )

    # ---------- Relación 1‑a‑1 con Usuario ----------
    usuario_id: int = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # mantiene la 1‑a‑1 a nivel de BD
    )
    usuario = db.relationship(
        "Usuario", back_populates="cliente", uselist=False
    )

    # ---------- Otras relaciones ----------
    pagos: List["Pago"] = db.relationship(
        "Pago",
        back_populates="cliente",
        cascade="all, delete-orphan",
    )
    asistencias: List["Asistencia"] = db.relationship(
        "Asistencia",
        back_populates="cliente",
        cascade="all, delete-orphan",
    )
    progresos: List["ProgresoCliente"] = db.relationship(
        "ProgresoCliente",
        back_populates="cliente",
        cascade="all, delete-orphan",
    )
    fotos: List["Foto"] = db.relationship(
        "Foto",
        back_populates="cliente",
        cascade="all, delete-orphan",
        lazy="select",
    )

    # ───────────────────────────────────── VALIDACIONES ────────────────────── #
    @validates("telefono")
    def _validate_telefono(self, key: str, value: Optional[str]) -> Optional[str]:
        """
        Solo dígitos y un posible ‘+’ al inicio.
        Longitud 5‑20 caracteres.
        """
        if value is None:
            return None
        if not re.fullmatch(r"^\+?\d{5,20}$", value):
            raise ValueError(
                "El teléfono debe contener entre 5 y 20 dígitos y puede "
                "comenzar con ‘+’."
            )
        return value

    @validates("correo")
    def _validate_correo(self, key: str, value: Optional[str]) -> Optional[str]:
        """
        Validación muy básica: contiene ‘@’ y ‘.’.
        El valor se guarda en minúsculas.
        """
        if value is None:
            return None
        if "@" not in value or "." not in value:
            raise ValueError("Dirección de correo inválida.")
        return value.lower()

    # ─────────────────────── MÉTODOS DE NEGOCIO ─────────────────────── #
    def activar_membresia(self, duracion_dias: int = 30) -> None:
        """Activa la membresía y calcula la fecha de vencimiento."""
        self.estado_membresia = EstadoMembresia.ACTIVO
        self.fecha_ingreso = datetime.utcnow()
        self.membresia_vencimiento = self.fecha_ingreso + timedelta(days=duracion_dias)

    def dias_restantes(self) -> Optional[int]:
        """Retorna el número de días que quedan para vencer la membresía."""
        if self.membresia_vencimiento is None:
            return None
        delta = self.membresia_vencimiento - datetime.utcnow()
        return delta.days  # >0 → días faltantes, <0 → días vencidos

    def membresia_activa(self) -> bool:
        """True cuando la membresía está marcada como ACTIVO y no ha vencido."""
        return (
            self.estado_membresia == EstadoMembresia.ACTIVO
            and self.membresia_vencimiento
            and self.membresia_vencimiento > datetime.utcnow()
        )

    # ───────────────────────── SERIALIZACIÓN ───────────────────────── #
    
    def to_dict(self, include_relations: bool = False) -> Dict:
        """Convierte el objeto a `dict` JSON‑friendly."""
        data: Dict = {
            "id": self.id,
            "nombre": self.nombre,
            "cedula": self.cedula,
            "correo": self.correo,
            "telefono": self.telefono,
            "foto_perfil": self.foto_perfil, 
            "estado_membresia": self.estado_membresia.value,
            "fecha_ingreso": (
                self.fecha_ingreso.isoformat() if self.fecha_ingreso else None
            ),
            "membresia_vencimiento": (
                self.membresia_vencimiento.isoformat()
                if self.membresia_vencimiento
                else None
            ),
            "dias_restantes": self.dias_restantes(),
            "membresia_activa": self.membresia_activa(),
        }

        if include_relations:
            data["pagos"] = [p.to_dict() for p in self.pagos]  # noqa: WPS337
        return data

    # ───────────────────── REPR ────────────────────── #
    def __repr__(self) -> str:
        venc = (
            self.membresia_vencimiento.strftime("%Y-%m-%d")
            if self.membresia_vencimiento
            else "N/A"
        )
        return f"<Cliente {self.id} {self.nombre} ({self.estado_membresia.value}) Vence: {venc}>"

# ───────────────────── EVENT DE BIRTH ────────────────────── #
@event.listens_for(Cliente, "before_delete")
def _prevent_delete_if_payments(mapper, connection, target: Cliente) -> None:
    """
    Evita borrar un cliente que tiene pagos pendientes.
    Se puede cambiar a sueldos, soft‑delete, etc.
    """
    if target.pagos:
        raise ValueError(
            f"No es posible eliminar el cliente {target.id} – aún tiene "
            f"{len(target.pagos)} pagos registrados."
        )
