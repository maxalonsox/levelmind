# Backend de LevelMind

API de LevelMind con FastAPI, Pydantic, SQLAlchemy 2 y Alembic. Actualmente
permite persistir Goals y su jerarquía básica de planificación:

```text
Goal → Stage → Mission → Task
```

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
configura la conexión a PostgreSQL y debe usar el dialecto de SQLAlchemy para
psycopg 3:

```dotenv
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE
```

Para conectar Supabase, obtener la connection string del proyecto desde su
panel, colocarla únicamente en el `.env` local y adaptar el esquema inicial a
`postgresql+psycopg://` si fuera necesario. Conservar los parámetros de conexión
provistos por Supabase y codificar como URL los caracteres especiales de la
contraseña. No copiar credenciales en el código, la documentación ni Git.

`SUPABASE_URL` identifica el proyecto de Supabase Auth. El backend deriva de
esta URL el issuer y el endpoint JWKS usados para verificar access tokens:

```dotenv
SUPABASE_URL=https://your-project-ref.supabase.co
```

El preview de planificación usa un proveedor con API compatible con OpenAI.
El proveedor y el modelo se seleccionan exclusivamente mediante configuración:

```dotenv
AI_BASE_URL=https://compatible-provider.example/v1
AI_API_KEY=replace-with-provider-api-key
AI_MODEL=replace-with-provider-model
AI_TIMEOUT_SECONDS=30
```

`AI_BASE_URL` es opcional; si se omite, el SDK utiliza su endpoint
predeterminado. `AI_API_KEY` y `AI_MODEL` son obligatorios al invocar el
Planner, pero no para levantar la API ni ejecutar los health checks.

## Ejecutar la API

Con el entorno virtual activo y desde `backend/`:

```bash
uvicorn app.main:app --reload
```

La API expone dos verificaciones públicas:

- `GET /health` confirma que la aplicación FastAPI está disponible, sin acceder
  a PostgreSQL.
- `GET /ready` ejecuta un `SELECT 1` para confirmar que SQLAlchemy y psycopg
  pueden comunicarse con PostgreSQL. Devuelve HTTP 503 si la conexión falla.

`POST /goals` requiere un access token de Supabase Auth mediante
`Authorization: Bearer <token>`. El propietario del Goal se obtiene del claim
`sub` verificado; `user_id` no forma parte del body.

La estructura de planificación expone estos endpoints, también autenticados:

- `POST /goals/{goal_id}/stages`
- `GET /goals/{goal_id}/stages`
- `POST /stages/{stage_id}/missions`
- `GET /stages/{stage_id}/missions`
- `POST /missions/{mission_id}/tasks`
- `GET /missions/{mission_id}/tasks`
- `POST /goals/{goal_id}/plan/preview`

Las consultas devuelven únicamente recursos del usuario autenticado y ordenan
los resultados por `order_index` ascendente.

`POST /goals/{goal_id}/plan/preview` verifica ownership y devuelve un
`GeneratedPlan` validado sin persistir Stages, Missions ni Tasks. Ejemplo:

```bash
curl -X POST http://127.0.0.1:8000/goals/<GOAL_ID>/plan/preview \
  -H "Authorization: Bearer <SUPABASE_ACCESS_TOKEN>"
```

Probarlas manualmente con:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/ready
```

## Ejecutar tests

```bash
pytest
```

Los tests no requieren una base de datos activa, un proyecto Supabase real ni
acceso a un proveedor de IA. La persistencia usa SQLite en memoria, la identidad
autenticada y el proveedor se reemplazan mediante dependency overrides, y el
chequeo de `/ready` se aísla.

## Alembic

Alembic obtiene la URL de conexión desde `DATABASE_URL`. Algunos comandos
básicos son:

```bash
alembic current
alembic revision --autogenerate -m "describe schema change"
alembic upgrade head
```

Los comandos que consultan o modifican el esquema requieren una instancia
PostgreSQL accesible. Las migraciones crean el Goal y su jerarquía de
planificación con foreign keys, índices y restricciones de dominio.
