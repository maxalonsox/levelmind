# Backend de LevelMind

Bootstrap mínimo de la API de LevelMind con FastAPI, Pydantic, SQLAlchemy 2 y
Alembic. En esta etapa no contiene lógica de negocio ni modelos de dominio.

## Preparación local

Desde `backend/`, crear y activar un entorno virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Instalar la aplicación y las dependencias de desarrollo:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Crear la configuración local a partir del ejemplo:

```bash
cp .env.example .env
```

El archivo `.env` está ignorado por Git y nunca debe commitearse. `DATABASE_URL`
es la única configuración de conexión a PostgreSQL y debe usar el dialecto de
SQLAlchemy para psycopg 3:

```dotenv
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE
```

Para conectar Supabase, obtener la connection string del proyecto desde su
panel, colocarla únicamente en el `.env` local y adaptar el esquema inicial a
`postgresql+psycopg://` si fuera necesario. Conservar los parámetros de conexión
provistos por Supabase y codificar como URL los caracteres especiales de la
contraseña. No copiar credenciales en el código, la documentación ni Git.

## Ejecutar la API

Con el entorno virtual activo y desde `backend/`:

```bash
uvicorn app.main:app --reload
```

La API expone dos verificaciones:

- `GET /health` confirma que la aplicación FastAPI está disponible, sin acceder
  a PostgreSQL.
- `GET /ready` ejecuta un `SELECT 1` para confirmar que SQLAlchemy y psycopg
  pueden comunicarse con PostgreSQL. Devuelve HTTP 503 si la conexión falla.

Probarlas manualmente con:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/ready
```

## Ejecutar tests

```bash
pytest
```

Los tests de health y readiness no requieren una base de datos activa; el
chequeo de conexión se reemplaza durante las pruebas de `/ready`.

## Alembic

Alembic obtiene la URL de conexión desde `DATABASE_URL`. Algunos comandos
básicos son:

```bash
alembic current
alembic revision --autogenerate -m "describe schema change"
alembic upgrade head
```

Los comandos que consultan o modifican el esquema requieren una instancia
PostgreSQL accesible. En esta etapa no existen migraciones de dominio.
