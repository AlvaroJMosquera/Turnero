from datetime import timedelta, date
from typing import Dict, List
from sqlalchemy.orm import Session, joinedload
import calendar
from models import Worker, Office, WorkerAssignment, OfficeShiftRequirement


def generate_schedule(worker: Worker, start_date: date, end_date: date) -> List[Dict]:
    dias = []
    fecha_actual = start_date

    vacaciones = sorted(worker.vacaciones, key=lambda v: v.fecha_inicio)
    ciclo_turnos = ["Mañana", "Mañana", "Libre", "Libre", "Tarde", "Tarde", "Libre", "Libre"]
    ciclo_index = 0

    while fecha_actual <= end_date:
        en_vacaciones = any(v.fecha_inicio <= fecha_actual <= v.fecha_fin for v in vacaciones)

        if en_vacaciones:
            turno = "Vacaciones"
        else:
            turno = ciclo_turnos[ciclo_index % len(ciclo_turnos)]
            ciclo_index += 1

        dias.append({
            "fecha": fecha_actual.isoformat(),
            "turno": turno
        })
        fecha_actual += timedelta(days=1)

    return dias


def asignar_y_guardar_turnos(db: Session):
    oficinas = db.query(Office).options(joinedload(Office.requerimientos)).all()
    trabajadores = db.query(Worker).options(joinedload(Worker.vacaciones)).all()

    hoy = date.today()
    prox_mes = hoy.month + 1 if hoy.month < 12 else 1
    year = hoy.year if prox_mes != 1 else hoy.year + 1

    ultimo_dia = calendar.monthrange(year, prox_mes)[1]
    start = date(year, prox_mes, 1)
    end = date(year, prox_mes, ultimo_dia)

    db.query(WorkerAssignment).filter(
        WorkerAssignment.fecha.between(start, end)
    ).delete(synchronize_session=False)
    db.flush()

    calendario: Dict[int, List[Dict]] = {
        t.id: generate_schedule(t, start, end) for t in trabajadores
    }

    asignaciones_diarias = {}

    for oficina in oficinas:
        requerimientos = {
            req.turno: req.cantidad for req in oficina.requerimientos
        }

        current = start
        while current <= end:
            for turno in ["Mañana", "Tarde"]:
                cantidad_requerida = requerimientos.get(turno, 0)
                asignados = []

                for t in trabajadores:
                    if len(asignados) >= cantidad_requerida:
                        break

                    dia_trabajador = next(
                        (d for d in calendario[t.id] if d["fecha"] == current.isoformat()),
                        None
                    )
                    ya_asignado = asignaciones_diarias.get((t.id, current, turno), False)

                    if (
                        dia_trabajador and
                        dia_trabajador["turno"] == turno and
                        not ya_asignado
                    ):
                        asignacion = WorkerAssignment(
                            worker_id=t.id,
                            office_id=oficina.id,
                            fecha=current,
                            turno=turno
                        )
                        db.add(asignacion)
                        asignaciones_diarias[(t.id, current, turno)] = True
                        asignados.append(t.id)

            current += timedelta(days=1)

    db.commit()
    return {"mensaje": "Asignaciones guardadas exitosamente."}
