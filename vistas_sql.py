from sqlalchemy import text
from sqlalchemy.orm import Session

def crear_vista_asignacion_si_no_existe(db: Session):
    sql = """
    CREATE OR REPLACE VIEW Asignacion AS
    SELECT 
        wa.id,
        CONCAT(w.nombre, ' ', w.apellidos) AS trabajador,
        r.nombre AS cargo,
        o.nombre AS oficina,
        wa.fecha,
        wa.turno
    FROM worker_assignments wa
    JOIN workers w ON wa.worker_id = w.id
    JOIN roles r ON w.cargo_id = r.id
    JOIN offices o ON wa.office_id = o.id;
    """
    db.execute(text(sql))
    db.commit()
