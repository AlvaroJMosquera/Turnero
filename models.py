from sqlalchemy import Column, Integer, String, Date, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, date
from database import Base
from pydantic import BaseModel
from typing import Optional, List

# ===================== #
#      MODELOS ORM      #
# ===================== #

class Worker(Base):
    __tablename__ = "workers"

    id = Column(Integer, primary_key=True, index=True)
    cedula = Column(String(20), unique=True, index=True, nullable=False)
    nombre = Column(String(100))
    apellidos = Column(String(100))
    cargo = Column(String(100))
    celular = Column(String(20), nullable=True)
    telefono = Column(String(20), nullable=True)
    direccion = Column(String(255), nullable=True)
    fecha_ingreso = Column(Date)
    fecha_nacimiento = Column(Date)
    creado_en = Column(DateTime, default=datetime.utcnow)

    office_id = Column(Integer, ForeignKey("offices.id"), nullable=True)
    oficina = relationship("Office")

    registros = relationship("Record", back_populates="trabajador")
    vacaciones = relationship("Vacation", back_populates="trabajador")


class Record(Base):
    __tablename__ = "records"

    id = Column(Integer, primary_key=True, index=True)
    trabajador_id = Column(Integer, ForeignKey("workers.id"))
    fecha = Column(Date, default=datetime.utcnow)
    salario = Column(Float)
    dias_trabajados = Column(Integer)
    observacion = Column(String(255), nullable=True)

    trabajador = relationship("Worker", back_populates="registros")


class Vacation(Base):
    __tablename__ = "vacations"

    id = Column(Integer, primary_key=True, index=True)
    worker_id = Column(Integer, ForeignKey("workers.id"))
    fecha_inicio = Column(Date, nullable=False)
    fecha_fin = Column(Date, nullable=False)

    trabajador = relationship("Worker", back_populates="vacaciones")


class Office(Base):
    __tablename__ = "offices"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False, unique=True)
    descripcion = Column(String(20), nullable=True)

    requerimientos = relationship("OfficeShiftRequirement", back_populates="office", cascade="all, delete-orphan")


class OfficeShiftRequirement(Base):
    __tablename__ = "office_shift_requirements"

    id = Column(Integer, primary_key=True, index=True)
    office_id = Column(Integer, ForeignKey("offices.id"))
    turno = Column(String(10), nullable=False)  
    cantidad = Column(Integer, nullable=False)

    office = relationship("Office", back_populates="requerimientos")


class WorkerAssignment(Base):
    __tablename__ = "worker_assignments"

    id = Column(Integer, primary_key=True, index=True)
    worker_id = Column(Integer, ForeignKey("workers.id"))
    office_id = Column(Integer, ForeignKey("offices.id"))
    fecha = Column(Date, nullable=False)
    turno = Column(String(10), nullable=False)

    worker = relationship("Worker")
    office = relationship("Office")

# ========================== #
#     MODELOS Pydantic       #
# ========================== #

# --- Worker ---
class WorkerCreate(BaseModel):
    cedula: str
    nombre: str
    apellidos: str
    cargo: str
    celular: Optional[str] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    fecha_ingreso: date
    fecha_nacimiento: date
    office_id: Optional[int] = None  

    class Config:
        from_attributes = True


# --- Record ---
class RecordCreate(BaseModel):
    trabajador_id: int
    fecha: date
    salario: float
    dias_trabajados: int
    observacion: Optional[str] = None

    class Config:
        orm_mode = True


# --- Vacation ---
class VacationCreate(BaseModel):
    worker_id: int
    fecha_inicio: date
    fecha_fin: date


class VacationOut(BaseModel):
    id: int
    worker_id: int
    fecha_inicio: date
    fecha_fin: date

    class Config:
        from_attributes = True


# --- Office ---
class OfficeBase(BaseModel):
    nombre: str
    descripcion: Optional[str] = None


class OfficeCreate(OfficeBase):
    pass


# --- Shift Requirement ---
class ShiftRequirementBase(BaseModel):
    turno: str
    cantidad: int


class ShiftRequirementCreate(ShiftRequirementBase):
    pass


# --- Assignment ---
class Assignment(BaseModel):
    fecha: date
    turno: str
    worker_id: int
    office_id: int
