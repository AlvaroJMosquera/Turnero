from datetime import timedelta, date
from typing import Dict, List
from sqlalchemy.orm import Session, joinedload
import calendar
from models import Worker, Office, WorkerAssignment, OfficeShiftRequirement
import random
from collections import defaultdict

def generate_schedule(worker: Worker, start_date: date, end_date: date) -> List[Dict]:
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
    trabajadores = db.query(Worker).options(joinedload(Worker.vacaciones), joinedload(Worker.rol)).all()

    hoy = date.today()
    start = date(hoy.year, hoy.month, 1)
    next_month = hoy.month + 1 if hoy.month < 12 else 1
    next_year = hoy.year + 1 if next_month == 1 else hoy.year
    last_day = calendar.monthrange(next_year, next_month)[1]
    end = date(next_year, next_month, last_day)

    db.query(WorkerAssignment).filter(
        WorkerAssignment.fecha.between(start, end)
    ).delete(synchronize_session=False)
    db.flush()

    resumen = []

    for oficina in oficinas:
        trabajadores_oficina = [t for t in trabajadores if t.office_id == oficina.id and t.rol is not None]

        cargos = {}
        for t in trabajadores_oficina:
            rol_nombre = t.rol.nombre
            cargos.setdefault(rol_nombre, []).append(t)

        ciclos = {}
        for grupo in cargos.values():
            for t in grupo:
                turno_inicial = random.choice(["Mañana", "Tarde"])
                ciclos[t.id] = {
                    "turno_actual": turno_inicial,
                    "dias_trabajados": 0,
                    "dias_descanso": 0,
                    "vacaciones": [(v.fecha_inicio, v.fecha_fin) for v in t.vacaciones],
                    "historial": [],
                    "horas_por_semana": defaultdict(int)
                }

        fecha = start
        while fecha <= end:
            semana_actual = fecha.isocalendar().week
            for turno in ["Mañana", "Tarde"]:
                hora_inicio = "7:00:00" if turno == "Mañana" else "19:00:00"
                hora_fin = "19:00:00" if turno == "Mañana" else "7:00:00"
                duracion_turno = 12

                requerimientos = [r for r in oficina.requerimientos if r.turno == turno]

                for req in requerimientos:
                    cargo = req.cargo
                    grupo = cargos.get(cargo, [])
                    random.shuffle(grupo)
                    cantidad_requerida = req.cantidad
                    asignados = 0

                    for t in grupo:
                        if asignados >= cantidad_requerida:
                            break

                        estado = ciclos[t.id]
                        historial = estado["historial"]

                        if any(start_v <= fecha <= end_v for start_v, end_v in estado["vacaciones"]):
                            continue
                        if any(h["fecha"] == fecha for h in historial):
                            continue

                        dias_consecutivos = 1
                        for i in range(1, 4):
                            if any(h["fecha"] == fecha - timedelta(days=i) for h in historial):
                                dias_consecutivos += 1
                            else:
                                break

                        if estado["dias_descanso"] > 0:
                            estado["dias_descanso"] -= 1
                            continue

                        if estado["horas_por_semana"][semana_actual] + duracion_turno > 44:
                            continue

                        if dias_consecutivos > 3:
                            continue

                        if estado["turno_actual"] != turno:
                            continue

                        db.add(WorkerAssignment(
                            worker_id=t.id,
                            office_id=oficina.id,
                            fecha=fecha,
                            turno=turno
                        ))

                        historial.append({"fecha": fecha, "turno": turno})
                        estado["dias_trabajados"] += 1
                        estado["horas_por_semana"][semana_actual] += duracion_turno
                        asignados += 1

                        if estado["dias_trabajados"] >= 2:
                            estado["dias_trabajados"] = 0
                            estado["dias_descanso"] = 2
                            estado["turno_actual"] = "Tarde" if estado["turno_actual"] == "Mañana" else "Mañana"

                        resumen.append({
                            "fecha": fecha.isoformat(),
                            "turno": turno,
                            "hora_inicio": hora_inicio,
                            "hora_fin": hora_fin,
                            "trabajador": f"{t.nombre} {t.apellidos}",
                            "cargo": cargo,
                            "oficina": oficina.nombre
                        })

                    if asignados < cantidad_requerida:
                        for _ in range(cantidad_requerida - asignados):
                            resumen.append({
                                "fecha": fecha.isoformat(),
                                "turno": turno,
                                "hora_inicio": hora_inicio,
                                "hora_fin": hora_fin,
                                "trabajador": "No disponible",
                                "cargo": cargo,
                                "oficina": oficina.nombre
                            })

            fecha += timedelta(days=1)

    db.commit()
    return {"resumen": resumen}
