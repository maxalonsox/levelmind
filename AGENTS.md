# Guía de desarrollo de LevelMind

Este documento establece las decisiones permanentes que deben respetar Codex y cualquier otro agente de desarrollo que trabaje en este repositorio. Antes de hacer cambios, leer también la documentación relevante en `docs/`, en particular `docs/mvp.md` y `docs/architecture.md`.

## Propósito y flujo conceptual

LevelMind es una plataforma de planificación adaptativa de objetivos profesionales y de aprendizaje.

El flujo conceptual principal es:

> Objetivo → Etapas → Misiones → Tareas

El usuario ejecuta tareas y proporciona feedback. El sistema evalúa el progreso y puede proponer adaptaciones al plan. Los cambios importantes requieren intervención humana (Human-in-the-Loop, HITL): nunca deben aplicarse silenciosamente.

## Stack decidido

### Frontend

- React
- TypeScript
- Vite

### Backend

- Python
- FastAPI
- Pydantic

### Persistencia

- PostgreSQL alojado mediante Supabase
- SQLAlchemy 2
- Alembic

### Autenticación

- Supabase Auth

### Orquestación agéntica

- LangGraph

No sustituir estas decisiones ni incorporar tecnologías adicionales sin una decisión arquitectónica explícita.

## Principios arquitectónicos

### Fuente de verdad y escritura

PostgreSQL es el *source of truth* de LevelMind. El estado de LangGraph, los prompts y las ventanas de contexto de los modelos no reemplazan la persistencia.

La IA no escribe directamente en la base de datos. Todo cambio generado por IA debe recorrer este flujo:

> LLM → validación Pydantic → validación de dominio → HITL cuando corresponda → transacción → PostgreSQL

Toda salida de IA que afecte al sistema debe usar modelos Pydantic o *structured outputs* y superar las validaciones correspondientes.

### Lógica determinista

La lógica determinista vive en código tradicional, no en prompts ni en decisiones no verificadas del modelo. Esto incluye:

- persistencia;
- autorización;
- progreso;
- XP;
- validaciones;
- invariantes;
- transiciones de estado;
- idempotencia.

### Responsabilidades cognitivas

Las responsabilidades cognitivas iniciales son:

- **Goal Analyzer:** analiza el objetivo y el contexto inicial del usuario;
- **Planner:** propone una estrategia y un plan estructurado;
- **Evaluator:** interpreta métricas y feedback para evaluar si el plan sigue siendo adecuado;
- **Adaptation Planner:** propone cambios concretos al plan cuando la evaluación lo justifica.

Estas responsabilidades deben implementarse principalmente como nodos especializados de workflows. No son agentes autónomos permanentes que conversan libremente entre sí.

### Separación de conceptos

Mantener separados explícitamente:

- **Goal:** qué quiere conseguir el usuario;
- **Plan:** la estrategia actual para conseguirlo;
- **Progress:** lo que ocurrió realmente durante la ejecución.

También distinguir:

- **user preferences:** información declarada explícitamente por el usuario;
- **user insights:** patrones inferidos a partir de evidencia, con confianza y trazabilidad adecuadas.

El Adaptation Planner puede proponer cambios al Plan, pero no modificar el Goal. Los cambios importantes deben presentarse al usuario para que pueda aceptarlos, modificarlos o rechazarlos.

### Plan vivo e histórico

El plan actual vive normalizado en tablas relacionales. El histórico se conserva mediante revisiones o snapshots inmutables en `plan_revisions`; no se debe clonar todo el árbol relacional con cada adaptación.

### Multiusuario y ownership

La arquitectura es multiusuario desde el inicio. Todas las consultas y mutaciones deben validar ownership y autorización. Conocer o proporcionar el ID de un recurso nunca es prueba suficiente de acceso.

## Restricciones de alcance

Mantener el MVP simple. No agregar, sin una decisión arquitectónica explícita:

- Vector DB;
- RAG;
- GraphRAG;
- fine-tuning;
- Redis;
- Celery;
- Kafka;
- Kubernetes;
- microservicios;
- swarms de agentes;
- calendario externo;
- notificaciones push;
- features sociales;
- marketplace;
- gamificación compleja.

## Modelo de dominio previsto

La arquitectura está preparada conceptualmente para las siguientes entidades:

- `profiles`;
- `user_preferences`;
- `user_insights`;
- `goals`;
- `plans`;
- `plan_revisions`;
- `stages`;
- `missions`;
- `tasks`;
- `task_feedback`;
- `adaptation_proposals`;
- `adaptation_changes`;
- `xp_events`;
- `workflow_jobs`;
- `ai_runs`.

Esta lista no es una instrucción para implementarlas todas de una vez. Preferir siempre un vertical slice pequeño que entregue comportamiento completo y verificable.

## Invariantes de dominio

- Una tarea completada no puede ser eliminada por una adaptación.
- El feedback histórico no se reescribe.
- El XP ganado no desaparece silenciosamente.
- El Adaptation Planner no puede modificar el Goal.
- Los cambios importantes requieren aprobación humana.
- Una propuesta generada para una revisión vieja del plan no puede aplicarse ciegamente sobre una revisión nueva.
- El modelo permite varios Goals, pero el MVP admite inicialmente sólo uno activo por usuario.
- Cada Goal tiene un único Plan vivo en el MVP.

Estas invariantes deben reforzarse en el dominio y, cuando corresponda, también mediante restricciones de base de datos y tests.

## Convenciones de base de datos

Preferir:

- UUID para identificadores;
- `TIMESTAMPTZ` para fechas y horas;
- `JSONB` únicamente cuando aporte flexibilidad real;
- enums de Python junto con restricciones `CHECK` en PostgreSQL, antes que tipos `ENUM` nativos de PostgreSQL;
- estilo de SQLAlchemy 2;
- Alembic como *source of truth* de los cambios permanentes de esquema.

No mantener manualmente el esquema mediante Supabase SQL Editor. Todo cambio permanente debe quedar representado en migraciones versionadas.

## Testing

- Los tests de funcionalidades de IA deben validar contratos, schemas, transiciones e invariantes; no texto exacto generado por el modelo.
- La lógica determinista debe tener tests unitarios tradicionales.
- Cuando corresponda, cubrir ownership, idempotencia, concurrencia y límites entre revisiones del plan.

## Forma de trabajo de Codex y otros agentes


Ante cada tarea:

1. Inspeccionar el repositorio y el estado de Git antes de modificar.
2. Leer la documentación relevante.
3. Hacer el cambio coherente más pequeño que resuelva la tarea.
4. No introducir tecnologías ni alcance no solicitados.
5. Ejecutar los tests y linters disponibles que correspondan al cambio.
6. Ejecutar `git diff --check`.
7. Revisar el diff final antes de cerrar la tarea.
8. Informar los archivos modificados.
9. Informar los comandos ejecutados.
10. Informar los tests, linters y validaciones ejecutados y sus resultados.
11. Explicitar los supuestos realizados.
12. Si una tarea entra en conflicto con la documentación arquitectónica, detenerse y señalar el conflicto en vez de decidir silenciosamente.
13. Si la tarea fue completada correctamente, crear un único commit coherente siguiendo Conventional Commits y hacer push de la rama actual, salvo que la instrucción de la tarea indique explícitamente lo contrario.
14. Informar el SHA del commit y el resultado del push.
15. No combinar cambios no relacionados en el mismo commit.

Preservar los cambios preexistentes del usuario y no modificar archivos fuera del alcance de la tarea.

### Convención de commits

Usar Conventional Commits.

Formato:

`<type>(<scope opcional>): <descripción breve>`

Tipos habituales:

- `feat`
- `fix`
- `docs`
- `refactor`
- `test`
- `chore`
- `build`
- `ci`
- `perf`

Ejemplos:

- `docs: add AGENTS and architecture documentation`
- `feat(goal): add goal creation endpoint`
- `fix(auth): validate authenticated user ownership`
- `test(planner): add structured output validation tests`

Los mensajes de commit deben:

- estar escritos en inglés;
- ser breves;
- describir un único cambio coherente;
- usar presente/imperativo;
- no terminar con punto.
