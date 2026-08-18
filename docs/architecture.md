# Arquitectura técnica inicial de LevelMind

## 1. Objetivo y alcance

LevelMind es una plataforma de planificación adaptativa para objetivos profesionales y de aprendizaje. Convierte el contexto de un usuario en un recorrido estructurado:

> Objetivo → Etapas → Misiones → Tareas

Esta arquitectura define los límites técnicos iniciales del MVP. Busca mantener la autoridad del dominio en código y PostgreSQL, mientras utiliza IA para analizar, interpretar y proponer. No incorpora funcionalidades fuera de las definidas en `docs/mvp.md`.

## 2. Arquitectura de alto nivel

```text
React + TypeScript + Vite
             │
             ▼
          FastAPI
         ╱       ╲
        ▼         ▼
 SQLAlchemy 2   LangGraph
        │         │
        ▼         ▼
   PostgreSQL   AI Provider
    (Supabase)
        ▲
        │
  Supabase Auth
```

El frontend se comunica con FastAPI y no accede al dominio por vías paralelas. FastAPI autentica y autoriza las operaciones, ejecuta reglas de aplicación y coordina tanto la persistencia mediante SQLAlchemy como los workflows cognitivos mediante LangGraph.

Los componentes cumplen estos roles:

- **React + TypeScript + Vite:** interfaz web, experiencia interactiva y empaquetado del frontend.
- **FastAPI:** límite de entrada del backend y coordinador de los casos de uso.
- **Pydantic:** contratos de API y validación de todas las salidas estructuradas de IA que puedan afectar al sistema.
- **SQLAlchemy 2:** acceso transaccional al modelo relacional.
- **PostgreSQL en Supabase:** estado autoritativo de usuarios, objetivos, planes, progreso, feedback y trazabilidad.
- **Supabase Auth:** identidad de usuario; el backend debe validar la identidad y el ownership de cada recurso.
- **LangGraph:** orquestación de workflows cognitivos, sus bifurcaciones y puntos de intervención humana.
- **AI Provider:** ejecución de modelos de lenguaje detrás de una abstracción que evita acoplar el dominio a un proveedor o modelo concreto.

## 3. Separación de responsabilidades

### Frontend

El frontend es responsable de:

- interacción con el usuario;
- onboarding;
- Home, plan activo y visualización de progreso;
- edición permitida del plan y sus tareas;
- captura de ejecución y feedback;
- interfaces HITL para revisar, aceptar o rechazar propuestas. La modificación
  inline de propuestas queda como evolución futura.

No contiene la autoridad final sobre reglas, permisos, progreso ni transiciones de estado.

### FastAPI y backend

FastAPI y sus servicios de aplicación son responsables de:

- exponer la API;
- validar autenticación y autorización;
- comprobar ownership además de los IDs recibidos;
- coordinar casos de uso y transacciones;
- ejecutar reglas e invariantes de dominio;
- calcular progreso, XP y métricas deterministas;
- coordinar persistencia y workflows;
- validar outputs de IA antes de utilizarlos.

### PostgreSQL

PostgreSQL es el *source of truth*. Conserva el estado autoritativo del producto y la trazabilidad necesaria. El estado de LangGraph, un prompt o la ventana de contexto de un LLM nunca sustituyen esa persistencia.

### LangGraph

LangGraph coordina workflows cognitivos, incluyendo:

- secuencia y branching entre nodos especializados;
- Planner, Evaluator y Adaptation Planner;
- pausas HITL y checkpoints cuando resulten útiles;
- reanudación y control de ejecuciones largas.

Estos roles son principalmente nodos especializados, no agentes autónomos persistentes conversando libremente entre sí.

### LLM

El LLM puede:

- analizar objetivos y contexto;
- planificar una estrategia;
- interpretar métricas y feedback;
- proponer adaptaciones.

El LLM nunca actúa como base de datos ni como autoridad de dominio. Tampoco escribe directamente en PostgreSQL. Un cambio propuesto por IA sigue siempre el circuito:

> LLM → validación Pydantic → validación de dominio → HITL cuando corresponda → transacción → PostgreSQL

Persistencia, autorización, progreso, XP, validaciones, invariantes, transiciones de estado e idempotencia se implementan mediante lógica determinista tradicional.

## 4. Workflows principales

### 4.1. Creación inicial

```text
Onboarding
    ↓
Goal persistido
    ↓
Planner
    ↓
Proposed Plan
    ↓
Validación Pydantic y de dominio
    ↓
Preview
    ↓
Usuario revisa y confirma
    ↓
Persistencia transaccional
```

El backend persiste el Goal con la información mínima del onboarding. El
Planner utiliza ese Goal para proponer el Plan. El resultado se valida antes de
mostrar el preview y sólo se persiste como jerarquía cuando el usuario lo
confirma.

### 4.2. Ciclo adaptativo

```text
Task execution
    ↓
Feedback
    ↓
Métricas deterministas
    ↓
Evaluator
    ↓
¿Adaptación necesaria?
    ├── no → continuar
    └── sí
          ↓
    Adaptation Planner
          ↓
    Adaptation Proposal
          ↓
         HITL
          ↓
    accept / reject
          ↓
    validación de dominio
          ↓
      transacción
          ↓
    nueva plan revision
          ↓
    continuar ciclo
```

Aceptar una propuesta no evita la validación de dominio. Al aplicar una
adaptación se comprueba que su revisión base siga vigente, se preserva el
histórico y se respetan las invariantes. Rechazarla también queda representado
como una decisión trazable. La edición inline del proposal no forma parte del
estado actual del MVP.

## 5. Estado y contexto de los modelos

`LangGraph State != LLM Context`.

Un workflow puede manejar un estado amplio para coordinar pasos, referencias persistidas, resultados intermedios y decisiones humanas. Eso no significa que cada llamada al modelo deba recibir todo ese estado. Cada nodo debe construir el contexto mínimo necesario para su responsabilidad.

Esta separación reduce ruido, costo y exposición innecesaria de datos; además facilita contratos claros y pruebas aisladas. El estado durable que importe al producto debe persistirse en PostgreSQL, no depender únicamente del grafo o de una ventana de contexto.

## 6. Datos y memoria

La memoria inicial de LevelMind distingue cuatro categorías:

- **Declared state:** objetivo, situación, disponibilidad y preferencias declaradas expresamente por el usuario.
- **Observed behavior:** tareas completadas, omitidas o no completadas, ritmo y modificaciones realizadas.
- **Explicit feedback:** dificultad informada y otras respuestas explícitas asociadas a la ejecución.
- **Inferred insights:** patrones inferidos a partir de evidencia, acompañados por su confianza y trazabilidad.

En el dominio, el **Goal** expresa qué quiere conseguir el usuario, el **Plan** representa la estrategia actual y el **Progress** registra lo que realmente ocurrió. No deben mezclarse ni sobrescribirse entre sí.

PostgreSQL cubre inicialmente estas necesidades mediante datos relacionales y, sólo donde aporte flexibilidad real, `JSONB`. El MVP no incorpora Vector DB, RAG ni GraphRAG porque LevelMind actualmente no tiene un problema de recuperación documental que lo justifique.

## 7. Modelo de datos conceptual

La arquitectura contempla conceptualmente `profiles`, `user_preferences`, `user_insights`, `goals`, `plans`, `plan_revisions`, `stages`, `missions`, `tasks`, `task_feedback`, `adaptation_proposals`, `adaptation_changes`, `xp_events`, `workflow_jobs` y `ai_runs`.

Esto no obliga a implementar todas las entidades al comienzo. Cada vertical slice debe incorporar únicamente las tablas y relaciones que necesita. El modelo debe soportar múltiples usuarios y validar ownership en todas las consultas. Aunque permite varios Goals, inicialmente el MVP admite sólo uno activo por usuario y un único Plan vivo por Goal.

## 8. Versionado del plan

`plans` representa el plan vivo. `stages`, `missions` y `tasks` representan su estado normalizado y consultable. `plan_revisions` conserva snapshots históricos inmutables para reconstruir qué plan estaba vigente en un momento dado, sin duplicar el árbol relacional completo como modelo operativo ante cada adaptación.

Una adaptación aceptada genera una nueva revisión. El snapshot puede registrarse inmediatamente antes o después de aplicar el cambio, según la estrategia transaccional que se defina al implementar el caso de uso, pero la operación debe ser atómica y su semántica inequívoca. Debe conservar:

- revisión base de la propuesta;
- cambios propuestos y finalmente aplicados;
- decisión humana;
- relación entre revisión anterior y nueva;
- trazabilidad suficiente para auditoría.

Una propuesta creada contra una revisión anterior no puede aplicarse ciegamente si el plan vivo ya cambió. Debe rechazarse como obsoleta o revalidarse explícitamente.

Las revisiones y adaptaciones también deben respetar estas invariantes:

- una tarea completada no se elimina;
- el feedback histórico no se reescribe;
- el XP ganado no desaparece silenciosamente;
- el Adaptation Planner no modifica el Goal;
- los cambios importantes requieren aprobación humana.

## 9. Evaluator híbrido

El Evaluator no debe recibir datos crudos y limitarse a “opinar” mediante IA. El backend calcula primero señales deterministas, por ejemplo:

- completion rate;
- dificultad reportada;
- tareas omitidas o no completadas;
- concentración de dificultad por skill;
- ritmo respecto de la disponibilidad declarada.

Después, el LLM interpreta esas señales junto con el contexto mínimo relevante y produce una salida estructurada. El código valida el contrato y decide, bajo reglas del dominio, cómo continuar el workflow. Los cálculos deterministas deben tener tests unitarios tradicionales; los tests de IA deben comprobar contratos e invariantes, no texto exacto.

## 10. Abstracción del proveedor de IA

Los workflows y el dominio deben depender de una interfaz propia para invocar capacidades de IA, no de APIs específicas de un proveedor. Esa abstracción normaliza solicitudes, structured outputs, errores y metadatos de ejecución.

Así se puede cambiar de proveedor o modelo sin modificar reglas de dominio,
persistencia ni contratos de aplicación. El MVP utiliza OpenRouter mediante su
API OpenAI-compatible; provider, endpoint y modelo se seleccionan por
configuración.

## 11. Procesamiento asíncrono

Las evaluaciones y adaptaciones actuales se ejecutan dentro del request HTTP,
con timeouts y reintentos acotados para errores transitorios del provider. Los
jobs persistidos o workers quedan fuera del MVP y sólo deberían evaluarse si la
carga y los requisitos operativos lo justifican. No se introducen Redis ni
Celery de forma anticipada.

## 12. Observabilidad de IA

Las ejecuciones de IA deben ser trazables. `ai_runs` puede registrar, cuando resulte apropiado:

- workflow;
- node;
- provider;
- model;
- prompt version;
- latency;
- token usage;
- validation status;
- error.

La observabilidad debe permitir diagnosticar una propuesta y relacionarla con su workflow y revisión del plan, sin persistir prompts, contexto ni información sensible innecesariamente. Los logs y registros deben aplicar minimización de datos.

## 13. Estrategia de implementación

LevelMind se construyó mediante vertical slices pequeños que atraviesan las
capas necesarias y entregan comportamiento verificable. El MVP actual cubre el
flujo autenticado desde la creación del Goal y el plan hasta la ejecución,
evaluación, adaptación HITL y persistencia de revisiones, sin implementar de
forma anticipada todas las entidades conceptuales.
