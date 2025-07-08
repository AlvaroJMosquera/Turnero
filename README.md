# Turnero de Vigilancia

Este proyecto en FastAPI permite gestionar trabajadores y generar turnos automáticos con la lógica 2x2 (2 días trabajo, 2 días descanso).

## Endpoints principales

- `POST /workers/` - Crear trabajador
- `GET /workers/` - Listar trabajadores
- `GET /schedule/{worker_id}?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` - Obtener turnos

## Cómo ejecutar

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Base de datos local SQLite: `workers.db`