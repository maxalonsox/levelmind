import { useState, type ReactNode } from 'react'

import type { PersistedStage, PersistedTask, PlanningStatus } from '../types/planning'
import { CollapsibleStage } from './CollapsibleStage'

interface ActivePlanHierarchyProps {
  stages: PersistedStage[]
  selectedTaskId: string | null
  onSelectTask: (task: PersistedTask) => void
  renderResolutionPanel: (task: PersistedTask) => ReactNode
}

const difficultyLabels = {
  easy: 'Fácil',
  normal: 'Normal',
  difficult: 'Difícil',
} as const

const statusLabels: Record<PlanningStatus, string> = {
  pending: 'Pendiente',
  in_progress: 'En progreso',
  completed: 'Completada',
  skipped: 'Finalizada con omisiones',
}

export function ActivePlanHierarchy({
  stages,
  selectedTaskId,
  onSelectTask,
  renderResolutionPanel,
}: ActivePlanHierarchyProps) {
  const [openStages, setOpenStages] = useState<Set<string>>(() => new Set())

  function toggleStage(stageId: string) {
    setOpenStages((current) => {
      const next = new Set(current)
      if (next.has(stageId)) next.delete(stageId)
      else next.add(stageId)
      return next
    })
  }

  return (
    <div className="plan-tree">
      {stages.map((stage, stageIndex) => {
        const taskCount = stage.missions.reduce((total, mission) => total + mission.tasks.length, 0)
        return (
          <CollapsibleStage
            className={`stage-card--${stage.status}`}
            key={stage.id}
            index={stageIndex}
            title={stage.title}
            description={stage.description}
            status={<StatusBadge status={stage.status} />}
            summary={`${stage.missions.length} ${stage.missions.length === 1 ? 'misión' : 'misiones'} · ${taskCount} ${taskCount === 1 ? 'tarea' : 'tareas'}`}
            isOpen={openStages.has(stage.id)}
            onToggle={() => toggleStage(stage.id)}
          >
            <div className="mission-list">
            {stage.missions.map((mission, missionIndex) => (
              <article className={`mission-card mission-card--${mission.status}`} key={mission.id}>
                <div className="mission-card__heading">
                  <div>
                    <span className="mission-card__index">Misión {missionIndex + 1}</span>
                    <div className="hierarchy-title-row">
                      <h3>{mission.title}</h3>
                      <StatusBadge status={mission.status} />
                    </div>
                    {mission.description && <p>{mission.description}</p>}
                  </div>
                  {mission.estimated_difficulty && (
                    <span className={`badge badge--${mission.estimated_difficulty}`}>
                      Estimación: {difficultyLabels[mission.estimated_difficulty]}
                    </span>
                  )}
                </div>

                <ol className="task-list">
                  {mission.tasks.map((task) => {
                    const isPending = task.status === 'pending'
                    const isSelected = selectedTaskId === task.id

                    return (
                      <li
                        className={`task-row task-row--active task-row--${task.status}`}
                        key={task.id}
                      >
                        <span className="task-row__marker" aria-hidden="true" />
                        <div className="task-row__content">
                          <div className="hierarchy-title-row">
                            <strong>{task.title}</strong>
                            <StatusBadge status={task.status} />
                          </div>
                          {task.description && <p>{task.description}</p>}
                          {task.feedback_text && (
                            <p className="task-row__feedback">“{task.feedback_text}”</p>
                          )}
                        </div>
                        <div className="task-row__metadata">
                          {task.estimated_duration_minutes && (
                            <span>{task.estimated_duration_minutes} min</span>
                          )}
                          {task.estimated_difficulty && (
                            <span>Estimación: {difficultyLabels[task.estimated_difficulty]}</span>
                          )}
                          {task.difficulty_feedback && (
                            <span className="task-feedback-badge">
                              Tu feedback: {difficultyLabels[task.difficulty_feedback]}
                            </span>
                          )}
                          <span>{task.xp_reward} XP</span>
                        </div>
                        {isPending && !isSelected && (
                          <button
                            className="button button--secondary button--small task-row__action"
                            onClick={() => onSelectTask(task)}
                          >
                            Registrar resultado
                          </button>
                        )}
                        {isSelected && (
                          <div className="task-row__resolution">{renderResolutionPanel(task)}</div>
                        )}
                      </li>
                    )
                  })}
                </ol>
              </article>
            ))}
            </div>
          </CollapsibleStage>
        )
      })}
    </div>
  )
}

function StatusBadge({ status }: { status: PlanningStatus }) {
  return <span className={`status-badge status-badge--${status}`}>{statusLabels[status]}</span>
}
