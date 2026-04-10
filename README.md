# 💳 SGC La Pipa — Backend

> Sistema de Gestión de Cupos (SGC) para La Pipa Comercializadora S.A.S.  
> Backend desarrollado como práctica profesional — Ingeniería de Sistemas y Telecomunicaciones.

---

## 📌 Descripción

API REST para la gestión integral de cupos y cartera financiera. Administra usuarios, fondos, asociados, microcréditos, ventas, entregas y auditoría, con control de acceso por roles (RBAC) y trazabilidad completa de operaciones.

---

## 🧠 Arquitectura

- **Framework:** FastAPI (Python 3.11+)
- **ORM:** SQLAlchemy 2.0 — modo asíncrono
- **Base de datos:** PostgreSQL 15
- **Migraciones:** Alembic
- **Autenticación:** JWT + OAuth2 + bcrypt
- **Tareas programadas:** APScheduler (expiración de microcupos cada 15 días)
- **Correo transaccional:** Resend API
- **Arquitectura modular** preparada para escalar

---

## 🗂️ Módulos del sistema (11)

| Módulo | Descripción |
|--------|-------------|
| MOD01 | Fondos |
| MOD02 | Usuarios |
| MOD03 | Asociados |
| MOD04 | Cupos y Cartera |
| MOD05 | Microcupos |
| MOD06 | Ventas y Entregas |
| MOD07 | Reportes |
| MOD08 | Auditoría |
| MOD09 | Dashboard |
| MOD10 | Puntos de Venta |
| MOD11 | IP Whitelist |

---

## 👥 Roles RBAC

- `ADMIN_GLOBAL`
- `ADMIN_FONDO`
- `EJECUTIVO_COMERCIAL`
- `TIENDA_OPERADOR`

---

## 🚀 Ejecución local

### Requisitos

- Python 3.11+
- PostgreSQL 15
- (Opcional) Docker y Docker Compose

### Con Docker

```bash
docker compose up --build
```

### Sin Docker

```bash
# Crear entorno virtual
python3.11 -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar migraciones
alembic upgrade head

# Iniciar servidor
uvicorn app.main:app --reload --port 8000
```

La API quedará disponible en:
- `http://localhost:8000`
- Documentación Swagger: `http://localhost:8000/docs`

---

## 🔐 Variables de entorno

Crea un archivo `.env` en la raíz del backend:

```env
DATABASE_URL=postgresql+asyncpg://usuario:password@host:5432/db
SECRET_KEY=genera-con-python-secrets
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
RESEND_API_KEY=re_xxxxxxxxxxxx
FRONTEND_URL=http://localhost:5173
SYSADMIN_EMAIL=admin@ejemplo.com
SYSADMIN_PASSWORD=password-inicial
IP_WHITELIST_ACTIVA=false
IPS_RESCATE=
```

> ⚠️ Nunca subas el archivo `.env` al repositorio.

---

## 🩺 Health Check

```
GET /health
```

Ejecuta un `SELECT 1` asíncrono contra la base de datos y retorna:

```json
{ "status": "ok", "db": 1 }
```

---

## 🧰 Stack tecnológico

| Tecnología | Uso |
|------------|-----|
| Python 3.11+ | Lenguaje principal |
| FastAPI | Framework API REST |
| SQLAlchemy 2.0 | ORM asíncrono |
| PostgreSQL 15 | Base de datos |
| Alembic | Migraciones |
| APScheduler | Tareas programadas |
| Resend | Correo transaccional |
| JWT + bcrypt | Autenticación |
| Docker | Entorno de desarrollo |

---

## 🔗 Repositorio Frontend

[sgc-la-pipa-frontend](https://github.com/jonatanalzate/sgc-la-pipa-frontend)

---

## 👨‍💻 Autor

**Jonatan Rojas Alzate**  
Ingeniero de Sistemas y Telecomunicaciones