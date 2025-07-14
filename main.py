from fastapi import Form
from fastapi.responses import RedirectResponse
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session, joinedload
from datetime import date, timedelta
from typing import List
import calendar

from database import Base, engine, SessionLocal
from models import (
    Worker, WorkerCreate, Vacation, VacationCreate,
    Office, OfficeShiftRequirement, WorkerAssignment, OfficeCreate, ShiftRequirementCreate,Role
)
from logic import generate_schedule, asignar_y_guardar_turnos

from vistas_sql import crear_vista_asignacion_si_no_existe
## Eliminar y crear tablas ###
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
## Crea la vista de asignacion 
db = SessionLocal()
crear_vista_asignacion_si_no_existe(db)
db.close()

def seed_roles(db: Session):
    nombres = ["Médico Veterinario", "Recepcionista"]
    for nombre in nombres:
        if not db.query(Role).filter_by(nombre=nombre).first():
            db.add(Role(nombre=nombre))
    db.commit()
with SessionLocal() as db:
    seed_roles(db)


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_start_end_of_month(year: int, month: int):
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)

@app.post("/workers/")
def create_worker(worker: WorkerCreate, db: Session = Depends(get_db)):
    if db.query(Worker).filter(Worker.cedula == worker.cedula).first():
        raise HTTPException(status_code=400, detail="Ya existe un trabajador con esa cédula.")
    db_worker = Worker(**worker.dict())
    db.add(db_worker)
    db.commit()
    db.refresh(db_worker)
    return db_worker

@app.get("/workers/")
def list_workers(db: Session = Depends(get_db)):
    trabajadores = db.query(Worker).options(joinedload(Worker.oficina)).all()
    return [
        {
            "id": w.id,
            "nombre": w.nombre,
            "apellidos": w.apellidos,
            "cedula": w.cedula,
            "cargo": w.rol.nombre if w.rol else None,
            "oficina": {"id": w.oficina.id, "nombre": w.oficina.nombre} if w.oficina else None
        }
        for w in trabajadores
    ]


@app.post("/workers/bulk/")
def create_workers_bulk(workers: List[WorkerCreate], db: Session = Depends(get_db)):
    created = []
    for worker in workers:
        if not db.query(Worker).filter(Worker.cedula == worker.cedula).first():
            db_worker = Worker(**worker.dict())
            db.add(db_worker)
            created.append(worker.cedula)
    db.commit()
    return {
        "mensaje": f"{len(created)} trabajadores creados exitosamente.",
        "cedulas_insertadas": created
    }

@app.delete("/workers/{worker_id}")
def delete_worker(worker_id: int, db: Session = Depends(get_db)):
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Trabajador no encontrado")

    # Eliminar asignaciones relacionadas
    db.query(WorkerAssignment).filter(WorkerAssignment.worker_id == worker_id).delete()

    db.delete(worker)
    db.commit()
    return {"message": "Trabajador y asignaciones eliminados correctamente"}

@app.post("/vacaciones/")
def crear_vacacion(vac: VacationCreate, db: Session = Depends(get_db)):
    trabajador = db.query(Worker).filter(Worker.id == vac.worker_id).first()
    if not trabajador:
        raise HTTPException(status_code=404, detail="Trabajador no encontrado")
    nueva = Vacation(**vac.dict())
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    return {"mensaje": "Vacaciones registradas", "vacacion_id": nueva.id}

@app.get("/vacaciones/lista/")
def listar_vacaciones(db: Session = Depends(get_db)):
    vacaciones = db.query(Vacation).all()
    resultado = []
    for v in vacaciones:
        trabajador = db.query(Worker).filter(Worker.id == v.worker_id).first()
        resultado.append({
            "nombre": trabajador.nombre,
            "apellidos": trabajador.apellidos,
            "cedula": trabajador.cedula,
            "fecha_inicio": v.fecha_inicio.isoformat(),  
            "fecha_fin": v.fecha_fin.isoformat()         
        })
    return JSONResponse(content=resultado)

@app.get("/workers/proximas-vacaciones/")
def trabajadores_proximos_a_vacaciones(db: Session = Depends(get_db)):
    hoy = date.today()
    en_30_dias = hoy + timedelta(days=30)
    trabajadores = db.query(Worker).options(joinedload(Worker.vacaciones)).all()
    proximos = []

    for t in trabajadores:
        for v in t.vacaciones:
            if hoy <= v.fecha_inicio <= en_30_dias:
                proximos.append({
                    "nombre": t.nombre,
                    "apellidos": t.apellidos,
                    "cedula": t.cedula,
                    "fecha_ingreso": str(t.fecha_ingreso),
                    "fecha_vacaciones": str(v.fecha_inicio)
                })
                break

    return proximos

@app.post("/offices/")
def create_office(office: OfficeCreate, db: Session = Depends(get_db)):
    nueva = Office(**office.dict())
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    return nueva

@app.get("/offices/")
def list_offices(db: Session = Depends(get_db)):
    return db.query(Office).all()

@app.delete("/offices/{office_id}")
def delete_office(office_id: int, db: Session = Depends(get_db)):
    office = db.query(Office).filter(Office.id == office_id).first()
    if not office:
        raise HTTPException(status_code=404, detail="Oficina no encontrada")
    db.delete(office)
    db.commit()
    return {"message": "Oficina eliminada correctamente"}

@app.post("/offices/{office_id}/requirements/")
def add_shift_requirements(office_id: int, requirements: List[ShiftRequirementCreate], db: Session = Depends(get_db)):
    oficina = db.query(Office).filter(Office.id == office_id).first()
    if not oficina:
        raise HTTPException(status_code=404, detail="Oficina no encontrada")
    for req in requirements:
        nuevo = OfficeShiftRequirement(office_id=office_id, turno=req.turno, cantidad=req.cantidad)
        db.add(nuevo)
    db.commit()
    return {"message": "Requisitos añadidos exitosamente"}

@app.get("/offices/{office_id}/requirements/")
def list_shift_requirements(office_id: int, db: Session = Depends(get_db)):
    return db.query(OfficeShiftRequirement).filter(OfficeShiftRequirement.office_id == office_id).all()

@app.get("/schedule/next-month/")
def schedule_all_next_month(db: Session = Depends(get_db)):
    today = date.today()
    next_month = today.month + 1 if today.month < 12 else 1
    year = today.year + 1 if next_month == 1 else today.year
    start_date, end_date = get_start_end_of_month(year, next_month)

    all_workers = db.query(Worker).options(joinedload(Worker.vacaciones)).all()
    result = []
    for worker in all_workers:
        turnos = generate_schedule(worker, start_date, end_date)
        result.append({
            "trabajador": f"{worker.nombre} {worker.apellidos}",
            "cedula": worker.cedula,
            "turnos": turnos
        })
    return result

@app.post("/asignaciones/generar/")
def generar_y_guardar_asignaciones(
    db: Session = Depends(get_db),
    anio: int = Form(...),
    mes: int = Form(...)
):
    start_date, end_date = get_start_end_of_month(anio, mes)
    resultado = asignar_y_guardar_turnos(db, start_date, end_date)
    return resultado


@app.get("/asignaciones/{office_id}/")
def ver_asignaciones_oficina(
    office_id: int,
    db: Session = Depends(get_db),
    anio: int = date.today().year,
    mes: int = date.today().month
):
    start, end = get_start_end_of_month(anio, mes)
    asignaciones = (
        db.query(WorkerAssignment)
        .options(joinedload(WorkerAssignment.worker).joinedload(Worker.rol),
                 joinedload(WorkerAssignment.office))
        .filter(
            WorkerAssignment.office_id == office_id,
            WorkerAssignment.fecha >= start,
            WorkerAssignment.fecha <= end
        )
        .all()
    )

    resultado = []
    for a in asignaciones:
        resultado.append({
            "fecha": a.fecha.isoformat(),
            "turno": a.turno,
            "hora_inicio": "07:00" if a.turno == "Mañana" else "19:00",
            "hora_fin": "19:00" if a.turno == "Mañana" else "07:00",
            "trabajador": f"{a.worker.nombre} {a.worker.apellidos}",
            "cargo": a.worker.rol.nombre if a.worker.rol else None,
            "oficina": a.office.nombre if a.office else None,
            "cedula": a.worker.cedula
        })

    return resultado

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/ver-turnos", response_class=HTMLResponse)
def ver_turnos(request: Request):
    return templates.TemplateResponse("ver_asignaciones.html", {"request": request})

@app.get("/ver-trabajadores", response_class=HTMLResponse)
def ver_trabajadores(request: Request):
    return templates.TemplateResponse("ver_trabajadores.html", {"request": request})

@app.get("/ver-vacaciones", response_class=HTMLResponse)
def ver_vacaciones(request: Request):
    return templates.TemplateResponse("vacaciones.html", {"request": request})

@app.get("/agregar-empleado", response_class=HTMLResponse)
def form_empleado(request: Request, db: Session = Depends(get_db)):
    roles = db.query(Role).all()
    oficinas = db.query(Office).all()
    return templates.TemplateResponse("agregar_empleado.html", {
        "request": request,
        "roles": roles,
        "oficinas": oficinas
    })

@app.get("/ver-oficinas", response_class=HTMLResponse)
def ver_oficinas(request: Request):
    return templates.TemplateResponse("oficinas.html", {"request": request})

@app.get("/asignar-turnos", response_class=HTMLResponse)
def asignar_turnos_view(request: Request):
    return templates.TemplateResponse("asignar_turnos.html", {"request": request})

@app.get("/ver-asignaciones", response_class=HTMLResponse)
def ver_asignaciones(request: Request):
    return templates.TemplateResponse("ver_asignaciones.html", {"request": request})

@app.get("/crear-oficina", response_class=HTMLResponse)
def form_crear_oficina(request: Request, db: Session = Depends(get_db)):
    roles = db.query(Role).all()
    return templates.TemplateResponse("crear_oficina.html", {"request": request, "roles": roles})

@app.post("/crear-oficina")
async def procesar_creacion_oficina(
    request: Request,
    db: Session = Depends(get_db)
):
    form = await request.form()

    nombre = form.get("nombre")
    descripcion = form.get("descripcion")

    turnos = form.getlist("turno")
    cargos = form.getlist("cargo")
    cantidades = form.getlist("cantidad")

    if not (len(turnos) == len(cargos) == len(cantidades)):
        raise HTTPException(status_code=400, detail="Datos de formulario incompletos.")

    nueva = Office(nombre=nombre, descripcion=descripcion)
    db.add(nueva)
    db.commit()
    db.refresh(nueva)

    requerimientos = []
    for turno, cargo, cantidad in zip(turnos, cargos, cantidades):
        cantidad_int = int(cantidad)
        if cantidad_int > 0:
            requerimientos.append(OfficeShiftRequirement(
                office_id=nueva.id,
                turno=turno,
                cargo=cargo,
                cantidad=cantidad_int
            ))

    db.add_all(requerimientos)
    db.commit()

    return RedirectResponse("/crear-oficina?success=1", status_code=303)

@app.get("/roles/")
def listar_roles(db: Session = Depends(get_db)):
    roles = db.query(Role).all()  # Asumiendo que tienes un modelo Role
    return [{"id": r.id, "nombre": r.nombre} for r in roles]

@app.get("/oficinas-con-requerimientos/")
def listar_oficinas_con_requerimientos(db: Session = Depends(get_db)):
    oficinas = db.query(Office).options(joinedload(Office.requerimientos)).all()
    resultado = []
    for o in oficinas:
        resultado.append({
            "id": o.id,
            "nombre": o.nombre.strip(),
            "descripcion": o.descripcion.strip() if o.descripcion else None,
            "requerimientos": [
                {
                    "turno": r.turno.strip(),
                    "cargo": r.cargo.strip(),
                    "cantidad": r.cantidad
                }
                for r in o.requerimientos
            ]
        })
    return resultado

