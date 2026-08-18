# LevelMind

LevelMind es una plataforma web asistida por IA que transforma objetivos
profesionales y de aprendizaje en un plan estructurado:

```text
Goal → Stage → Mission → Task
```

Combina planificación asistida por IA, seguimiento de progreso, evaluación y
propuestas de adaptación. Las decisiones importantes pasan por un flujo
Human-in-the-Loop (HITL): el usuario revisa los cambios antes de aplicarlos. El
MVP también incluye XP, nivel y porcentaje de progreso como gamificación básica.

## Problema que resuelve

Los objetivos profesionales suelen ser demasiado amplios para convertirlos
directamente en acciones. Además, un plan estático deja de ser útil cuando no
refleja la ejecución, las dificultades y el feedback reales. LevelMind propone
un ciclo en el que el objetivo se descompone en tareas concretas, se observa el
progreso y sólo se sugieren ajustes cuando existe evidencia suficiente.

## Flujo principal

```text
Registro / login
    ↓
Crear Goal
    ↓
Generar plan con IA
    ↓
Preview
    ↓
HITL: aceptar
    ↓
Plan activo
    ↓
Ejecutar Tasks
    ↓
Feedback + XP + progreso
    ↓
Evaluator
    ↓
¿Hay evidencia suficiente para adaptar?
    ├─ No → mantener plan
    └─ Sí
        ↓
    Adaptation Planner
        ↓
    HITL: aceptar / rechazar
        ↓
    Nueva revisión del plan
```

El LLM no escribe directamente en PostgreSQL. Sus respuestas estructuradas se
validan con Pydantic y reglas de dominio; después, el backend controla ownership,
invariantes, transacciones y stale protection. El usuario conserva el control
sobre la aceptación o el rechazo de cada adaptación.

## Funcionalidades actuales

- Registro, confirmación por email, login y logout mediante Supabase Auth.
- Un único Goal activo por usuario y recuperación de Goals todavía sin plan.
- Generación de planes mediante IA, preview y aceptación HITL.
- Jerarquía persistida de Stages, Missions y Tasks.
- Duraciones estimadas por Task y agregadas de forma derivada por Mission y Stage.
- Edición manual de título, descripción y duración de Tasks pendientes.
- Resultados `completed` y `skipped`, dificultad `easy` / `normal` / `difficult`
  y feedback textual.
- XP, nivel derivado y porcentaje de progreso.
- Evaluación del progreso con interpretación por IA y guardrails deterministas.
- Propuestas estructuradas de adaptación con aceptación o rechazo HITL.
- Revisiones inmutables del plan y protección frente a propuestas obsoletas.
- Persistencia PostgreSQL, ownership multiusuario y navegación guiada por el
  estado autoritativo del backend.

## Arquitectura técnica

- **Frontend:** React, TypeScript y Vite.
- **Backend:** Python, FastAPI, SQLAlchemy 2, Pydantic y Alembic.
- **Persistencia y autenticación:** PostgreSQL en Supabase y Supabase Auth.
- **IA:** OpenRouter mediante una API OpenAI-compatible y un provider abstraído.
  El Planner genera planes, el Evaluator interpreta evidencia y el Adaptation
  Planner propone cambios. LangGraph coordina el flujo adaptativo.

```text
Frontend
   ↓
FastAPI
   ↓
Domain / Services
   ├─ PostgreSQL
   └─ AI Provider
          ↓
      OpenRouter
```

Para el diseño completo, consultar [arquitectura](docs/architecture.md) y
[alcance del MVP](docs/mvp.md).

## Principios de diseño

- **Backend como source of truth:** `localStorage` sólo funciona como cache de
  navegación; nunca demuestra que exista un Goal activo.
- **Structured outputs:** todas las respuestas relevantes de IA pasan por
  schemas Pydantic y validaciones de dominio.
- **IA probabilística con guardrails deterministas:** el Evaluator interpreta
  contexto, pero el backend exige evidencia mínima y persistente antes de
  permitir una adaptación.
- **Human-in-the-Loop:** un plan o una adaptación no se aplica silenciosamente.
- **Estado derivado:** progreso, XP, nivel y duraciones agregadas se calculan a
  partir del estado persistido para evitar duplicación.

## Estructura del repositorio

```text
levelmind/
├── backend/
│   ├── app/
│   │   ├── ai/
│   │   ├── api/
│   │   ├── models/
│   │   ├── schemas/
│   │   └── services/
│   ├── alembic/
│   └── tests/
├── frontend/
│   └── src/
│       ├── api/
│       ├── auth/
│       ├── components/
│       ├── pages/
│       └── types/
└── docs/
```

## Preparación local

### Requisitos

- Python 3.12 o posterior.
- Node.js y npm compatibles con el lockfile del frontend.
- PostgreSQL accesible, local o mediante Supabase.
- Proyecto de Supabase para autenticación.
- API key y modelo disponibles en OpenRouter para los flujos de IA.

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

La API se inicia por defecto en `http://127.0.0.1:8000`; la documentación
interactiva de FastAPI queda disponible en `http://127.0.0.1:8000/docs`.
Consultar también el [README del backend](backend/README.md).

### Frontend

```bash
cd frontend
npm ci
cp .env.example .env
npm run dev
```

Vite utiliza por defecto `http://localhost:5173` durante el desarrollo local.

## Variables de entorno

No se deben commitear archivos `.env` ni valores secretos.

### Backend

| Variable | Uso |
| --- | --- |
| `APP_NAME` | Nombre expuesto por la API. |
| `APP_ENV` | Entorno de ejecución. |
| `DATABASE_URL` | Conexión SQLAlchemy a PostgreSQL mediante psycopg. |
| `SUPABASE_URL` | Proyecto usado para validar tokens de Supabase Auth. |
| `CORS_ALLOWED_ORIGINS` | Orígenes frontend permitidos, separados por comas. |
| `AI_BASE_URL` | Endpoint OpenAI-compatible; para OpenRouter se configura su URL de API. |
| `AI_API_KEY` | Credencial del proveedor de IA. |
| `AI_MODEL` | Modelo configurado para Planner, Evaluator y Adaptation Planner. |
| `AI_TIMEOUT_SECONDS` | Timeout de las solicitudes al proveedor. |

### Frontend

| Variable | Uso |
| --- | --- |
| `VITE_API_BASE_URL` | URL base del backend FastAPI. |
| `VITE_SUPABASE_URL` | URL del proyecto Supabase. |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | Clave pública utilizada por Supabase Auth. |

## Tests y validaciones

Backend, desde `backend/` con el entorno virtual activo:

```bash
pytest
python -m compileall -q app tests
alembic current
alembic heads
alembic check
```

Frontend, desde `frontend/`:

```bash
npm test -- --run
npm run typecheck
npm run lint
npm run build
```

Los tests automatizados aíslan PostgreSQL, Supabase Auth y los providers de IA
mediante mocks y dependency overrides.

## Estado actual del MVP

El flujo end-to-end principal está implementado: autenticación, planificación
por IA, aceptación del plan, ejecución y edición de Tasks, feedback, progreso,
evaluación, adaptaciones HITL y revisiones persistidas.

### Limitaciones conocidas

1. Las propuestas de adaptación pueden aceptarse o rechazarse. La modificación
   inline de una propuesta queda como evolución futura.
2. Los previews de IA no aceptados son efímeros y pueden requerir regeneración
   después de recargar la página.
3. La disponibilidad y latencia de OpenRouter afectan los flujos de IA.
4. Los tests con mocks no reemplazan un smoke test contra Supabase y OpenRouter
   reales.

## Demo flow

1. Registrarse o iniciar sesión.
2. Crear un Goal profesional.
3. Generar el plan con IA.
4. Revisar y aceptar el preview.
5. Editar una Task pendiente.
6. Completar u omitir Tasks y registrar dificultad y feedback.
7. Observar XP, nivel y progreso.
8. Solicitar una revisión del plan.
9. Mostrar que sin evidencia suficiente el plan se mantiene.
10. Con evidencia persistente, generar una propuesta de adaptación.
11. Aceptar o rechazar la propuesta.
12. Verificar el plan actualizado y su nueva revisión persistida.

## Fuera del MVP

Posibles evoluciones incluyen modificación inline de propuestas HITL,
achievements o streaks, integraciones con calendarios, mayor observabilidad de
IA, workflows asíncronos y expansión a Goals personales.
