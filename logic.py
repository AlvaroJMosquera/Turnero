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

def asignar_y_guardar_turnos(db: Session, start: date, end: date):
    oficinas = db.query(Office).options(joinedload(Office.requerimientos)).all()
    trabajadores = db.query(Worker).options(joinedload(Worker.vacaciones), joinedload(Worker.rol)).all()

    db.query(WorkerAssignment).filter(
        WorkerAssignment.fecha.between(start, end)
    ).delete(synchronize_session=False)
    db.flush()

    resumen = []

    for oficina in oficinas:
        trabajadores_oficina = [t for t in trabajadores if t.office_id == oficina.id and t.rol is not None]

        cargos = {}
        for t in trabajadores_oficina:
            rol_nombre = t.rol.nombre.strip()
            cargos.setdefault(rol_nombre, []).append(t)

        ciclos = {}
        for cargo, grupo in cargos.items():
            grupo_ordenado = sorted(grupo, key=lambda t: t.id)
            mitad = len(grupo_ordenado) // 2
            for i, t in enumerate(grupo_ordenado):
                turno_inicial = "Mañana" if i < mitad else "Tarde"
                ciclos[t.id] = {
                    "turno_actual": turno_inicial,
                    "dias_trabajados": 0,
                    "dias_descanso": 0,
                    "vacaciones": [(v.fecha_inicio, v.fecha_fin) for v in t.vacaciones],
                    "historial": [],
                    "horas_por_semana": defaultdict(int)
                }

        requerimientos_agrupados = defaultdict(int)
        for r in oficina.requerimientos:
            clave = (r.cargo.strip(), r.turno.strip())
            requerimientos_agrupados[clave] += r.cantidad

        fecha = start
        while fecha <= end:
            semana_actual = fecha.isocalendar().week
            for turno in ["Mañana", "Tarde"]:
                hora_inicio = "7:00:00" if turno == "Mañana" else "19:00:00"
                hora_fin = "19:00:00" if turno == "Mañana" else "7:00:00"
                duracion_turno = 12

                for (cargo, turno_req), cantidad_requerida in requerimientos_agrupados.items():
                    if turno_req != turno:
                        continue

                    grupo = cargos.get(cargo, [])
                    random.shuffle(grupo)
                    asignados = 0

                    for t in grupo:
                        estado = ciclos[t.id]
                        historial = estado["historial"]

                        if any(start_v <= fecha <= end_v for start_v, end_v in estado["vacaciones"]):
                            continue
                        if any(h["fecha"] == fecha for h in historial):
                            continue

                        dias_consecutivos = 0
                        for i in range(1, 4):
                            dia_anterior = fecha - timedelta(days=i)
                            if any(h["fecha"] == dia_anterior for h in historial):
                                dias_consecutivos += 1
                            else:
                                break

                        if dias_consecutivos >= 3:
                            continue

                        ya_tiene_turno_hoy = any(h["fecha"] == fecha and h["turno"] != turno for h in historial)
                        if ya_tiene_turno_hoy:
                            continue

                        if estado["horas_por_semana"][semana_actual] + duracion_turno > 48:
                            continue

                        if estado["dias_descanso"] > 0 and dias_consecutivos < 2:
                            estado["dias_descanso"] -= 1
                            continue

                        if estado["turno_actual"] != turno and dias_consecutivos < 2:
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

                        if asignados >= cantidad_requerida:
                            break

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

def trabajadores_disponibles(db: Session, fecha: date):
    trabajadores = db.query(Worker).options(joinedload(Worker.vacaciones), joinedload(Worker.rol)).all()
    disponibles = []
    for t in trabajadores:
        if any(v.fecha_inicio <= fecha <= v.fecha_fin for v in t.vacaciones):
            continue
        disponibles.append(f"{t.nombre} {t.apellidos} - {t.rol.nombre if t.rol else 'Sin rol'}")
    return disponibles
