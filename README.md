# SGC "La Pipa" - Sprint 1

Backend asíncrono con FastAPI y SQLAlchemy 2.0, dockerizado con Postgres.

## Requisitos

- Docker y Docker Compose instalados.

## Levantar el proyecto

```bash
docker compose up --build
```

La API quedará disponible en `http://localhost:8000` y la documentación en `http://localhost:8000/docs`.

## Healthcheck

- Endpoint: `GET /health`
- Ejecuta `SELECT 1` de forma asíncrona contra la base de datos en Docker.

