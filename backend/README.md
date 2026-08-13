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

El archivo `.env` está ignorado por Git. Ajustar `DATABASE_URL` para apuntar a
una instancia PostgreSQL disponible cuando sea necesario.

## Ejecutar la API

Con el entorno virtual activo y desde `backend/`:

```bash
uvicorn app.main:app --reload
```

El health check queda disponible en `http://127.0.0.1:8000/health`.

## Ejecutar tests

```bash
pytest
```

El test del health check no requiere una base de datos activa.

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
