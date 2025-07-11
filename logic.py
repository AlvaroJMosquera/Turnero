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


from datetime import date, timedelta
import calendar
from sqlalchemy.orm import Session, joinedload
from models import Worker, Office, WorkerAssignment, OfficeShiftRequirement


def generate_schedule(worker, start_date, end_date):
    dias = []
    fecha_actual = start_date
    vacaciones = sorted(worker.vacaciones, key=lambda v: v.fecha_inicio)
    ciclo_turnos = ["Mañana", "Mañana", "Libre", "Libre", "Tarde", "Tarde", "Libre", "Libre"]
    ciclo_index = 0

    while fecha_actual <= end_date:
        en_vacaciones = any(v.fecha_inicio <= fecha_actual <= v.fecha_fin for v in vacaciones)
        turno = "Vacaciones" if en_vacaciones else ciclo_turnos[ciclo_index % len(ciclo_turnos)]
        if not en_vacaciones:
            ciclo_index += 1
        dias.append({"fecha": fecha_actual.isoformat(), "turno": turno})
        fecha_actual += timedelta(days=1)

    return dias

def asignar_y_guardar_turnos(db: Session):
    oficinas = db.query(Office).options(joinedload(Office.requerimientos)).all()
    trabajadores = db.query(Worker).options(joinedload(Worker.vacaciones)).all()

    hoy = date.today()
    start = date(hoy.year, hoy.month, 1)
    if hoy.month == 12:
        next_month = 1
        next_year = hoy.year + 1
    else:
        next_month = hoy.month + 1
        next_year = hoy.year

    last_day = calendar.monthrange(next_year, next_month)[1]
    end = date(next_year, next_month, last_day)

    # Eliminar asignaciones anteriores del rango
    db.query(WorkerAssignment).filter(
        WorkerAssignment.fecha.between(start, end)
    ).delete(synchronize_session=False)
    db.flush()

    # Estructura de control por trabajador
    calendario = {}
    for t in trabajadores:
        calendario[t.id] = {
            "cargo": t.cargo,
            "vacaciones": [(v.fecha_inicio, v.fecha_fin) for v in t.vacaciones],
            "historial": [],
            "ultimo_turno": None,
            "dias_consecutivos": 0
        }

    resumen = []

    for oficina in oficinas:
        requerimientos = {r.turno: r.cantidad for r in oficina.requerimientos}
        current = start
        while current <= end:
            for turno in ["Mañana", "Tarde"]:
                hora_inicio = "7:00:00" if turno == "Mañana" else "19:00:00"
                hora_fin = "19:00:00" if turno == "Mañana" else "7:00:00"

                for cargo in ["Médico Veterinario", "Recepcionista"]:
                    cantidad_necesaria = requerimientos.get(turno, 0)
                    candidatos = []

                    for t in trabajadores:
                        if t.cargo != cargo:
                            continue
                        estado = calendario[t.id]

                        # En vacaciones
                        if any(vac[0] <= current <= vac[1] for vac in estado["vacaciones"]):
                            continue

                        # Ya tiene asignación ese día y turno
                        if any(a["fecha"] == current and a["turno"] == turno for a in estado["historial"]):
                            continue

                        # Revisión de días consecutivos
                        consecutivos = estado["dias_consecutivos"]
                        if consecutivos >= 3:
                            continue
                        if consecutivos == 2 and estado["ultimo_turno"] == turno:
                            continue

                        candidatos.append(t)

                    for seleccionado in candidatos[:cantidad_necesaria]:
                        db.add(WorkerAssignment(
                            worker_id=seleccionado.id,
                            office_id=oficina.id,
                            fecha=current,
                            turno=turno
                        ))

                        estado = calendario[seleccionado.id]
                        if estado["ultimo_turno"] == turno:
                            estado["dias_consecutivos"] += 1
                        else:
                            estado["dias_consecutivos"] = 1
                            estado["ultimo_turno"] = turno
                        estado["historial"].append({
                            "fecha": current,
                            "turno": turno
                        })

                        resumen.append({
                            "fecha": current.isoformat(),
                            "turno": turno,
                            "hora_inicio": hora_inicio,
                            "hora_fin": hora_fin,
                            "trabajador": f"{seleccionado.nombre} {seleccionado.apellidos}",
                            "cargo": seleccionado.cargo,
                            "oficina": oficina.nombre
                        })
            current += timedelta(days=1)

    db.commit()
    return {"resumen": resumen}