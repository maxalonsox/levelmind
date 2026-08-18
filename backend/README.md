# Backend de LevelMind

API de LevelMind con FastAPI, Pydantic, SQLAlchemy 2 y Alembic. Implementa el
flujo del MVP desde el Goal y la planificación asistida por IA hasta la
ejecución, evaluación, adaptación HITL y versionado del plan:

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

- `GET /goals/active`
- `DELETE /goals/{goal_id}`
- `POST /goals/{goal_id}/stages`
- `GET /goals/{goal_id}/stages`
- `POST /stages/{stage_id}/missions`
- `GET /stages/{stage_id}/missions`
- `POST /missions/{mission_id}/tasks`
- `GET /missions/{mission_id}/tasks`
- `POST /goals/{goal_id}/plan/preview`
- `POST /goals/{goal_id}/plan/accept`
- `GET /goals/{goal_id}/plan`
- `PATCH /tasks/{task_id}`
- `POST /tasks/{task_id}/result`
- `POST /goals/{goal_id}/evaluation/preview`
- `POST /goals/{goal_id}/adaptation/preview`
- `POST /goals/{goal_id}/adaptations/{adaptation_id}/accept`
- `POST /goals/{goal_id}/adaptations/{adaptation_id}/reject`

Las consultas devuelven únicamente recursos del usuario autenticado y ordenan
los resultados por `order_index` ascendente.

`POST /goals/{goal_id}/plan/preview` verifica ownership y devuelve un
`GeneratedPlan` validado sin persistir Stages, Missions ni Tasks. Ejemplo:

```bash
curl -X POST http://127.0.0.1:8000/goals/<GOAL_ID>/plan/preview \
  -H "Authorization: Bearer <SUPABASE_ACCESS_TOKEN>"
```

Después de revisar el JSON devuelto, guardar exactamente ese contenido, por
ejemplo en `generated-plan.json`, y aceptarlo sin volver a invocar al proveedor
de IA:

```bash
curl -X POST http://127.0.0.1:8000/goals/<GOAL_ID>/plan/accept \
  -H "Authorization: Bearer <SUPABASE_ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d @generated-plan.json
```

La aceptación devuelve HTTP 201 con la jerarquía persistida. Si el Goal ya
posee Stages, devuelve HTTP 409 y no agrega, reemplaza ni combina planes.

Consultar el plan vivo, sus estados, duraciones agregadas, progreso, XP y nivel
derivados:

```bash
curl http://127.0.0.1:8000/goals/<GOAL_ID>/plan \
  -H "Authorization: Bearer <SUPABASE_ACCESS_TOKEN>"
```

Registrar el resultado y feedback explícito de una Task:

```bash
curl -X POST http://127.0.0.1:8000/tasks/<TASK_ID>/result \
  -H "Authorization: Bearer <SUPABASE_ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "result": "completed",
    "difficulty_feedback": "normal",
    "feedback_text": "La validación requirió más debugging del esperado."
  }'
```

`result` admite únicamente `completed` o `skipped`. El XP y el porcentaje no
se reciben del cliente: se calculan a partir del estado persistido de las Tasks.
Repetir el mismo resultado es idempotente; intentar cambiar una Task terminal
a otro resultado devuelve HTTP 409.

Las Tasks pendientes permiten editar únicamente título, descripción y duración
estimada mediante `PATCH /tasks/{task_id}`. El backend revalida ownership y
rechaza con HTTP 409 cualquier Task que ya tenga un resultado terminal.

Solicitar una evaluación estructurada y no persistente del estado observado:

```bash
curl -X POST \
  http://127.0.0.1:8000/goals/<GOAL_ID>/evaluation/preview \
  -H "Authorization: Bearer <SUPABASE_ACCESS_TOKEN>"
```

Solicitar una propuesta estructurada de adaptación a partir de la evaluación y
el plan vivo:

```bash
curl -X POST \
  http://127.0.0.1:8000/goals/<GOAL_ID>/adaptation/preview \
  -H "Authorization: Bearer <SUPABASE_ACCESS_TOKEN>"
```

El flujo diario queda: registrar resultados de Tasks, consultar el plan,
solicitar el preview de evaluación y, cuando corresponda, solicitar el preview
de adaptación. Si hay menos de 2 Tasks resueltas, o hay exactamente 2 pero
representan menos del 20% del plan, la evaluación devuelve `insufficient_data`.
Si el resultado validado tiene `needs_adaptation=false`, el preview de
adaptación responde con `needs_adaptation=false`, un proposal `no_change` y
`adaptation=null`, sin construir ni invocar su proveedor de IA. Cuando el
proposal validado contiene cambios, se guarda como una `PlanAdaptation`
`pending` y la respuesta la expone en `adaptation`. Los campos existentes del
proposal permanecen en el nivel superior del response.

El preview de evaluación es de solo lectura. La propuesta de adaptación usa
índices de orden y títulos en lugar de UUIDs para identificar targets, se valida
contra el plan vivo y se persiste para revisión HITL, pero no se aplica.
El plan aceptado inicialmente crea la revisión base. Para planes existentes, la
primera revisión se crea de forma lazy antes de generar una nueva adaptación.
Cada adaptación queda vinculada a esa revisión y sólo puede aceptarse si sigue
siendo la revisión vigente:

```bash
curl -X POST \
  http://127.0.0.1:8000/goals/<GOAL_ID>/adaptations/<ADAPTATION_ID>/accept \
  -H "Authorization: Bearer <SUPABASE_ACCESS_TOKEN>"
```

La aceptación no invoca IA: revalida y aplica atómicamente el proposal
persistido, marca la adaptación como `accepted` y crea la siguiente revisión
inmutable del plan. Una adaptación ya revisada, obsoleta o con targets que ya no
coinciden devuelve HTTP 409. El endpoint `/reject` marca una adaptación pending
como `rejected` sin modificar el plan ni crear una revisión nueva. La
modificación inline de una propuesta todavía no está implementada.

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
PostgreSQL accesible. Las migraciones versionan el Goal, su jerarquía de
planificación, memoria, adaptaciones, revisiones e índices y restricciones de
dominio.
