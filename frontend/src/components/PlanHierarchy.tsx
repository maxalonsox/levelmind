import { useState } from 'react'

import type { PlanPreview } from '../types/planning'
import { CollapsibleStage } from './CollapsibleStage'

interface PlanHierarchyProps {
  preview: PlanPreview
}

const difficultyLabels = {
  easy: 'Fácil',
  normal: 'Normal',
  difficult: 'Difícil',
} as const

export function PlanHierarchy({ preview }: PlanHierarchyProps) {
  const stages = [...preview.stages].sort((left, right) => left.order_index - right.order_index)
  const [openStages, setOpenStages] = useState<Set<string>>(() => new Set())

  function toggleStage(stageKey: string) {
    setOpenStages((current) => {
      const next = new Set(current)
      if (next.has(stageKey)) next.delete(stageKey)
      else next.add(stageKey)
      return next
    })
  }

  return (
    <div className="plan-tree">
      {stages.map((stage, stageIndex) => {
        const stageKey = `${stage.order_index}-${stage.title}`
        const taskCount = stage.missions.reduce((total, mission) => total + mission.tasks.length, 0)
        return (
          <CollapsibleStage
            key={stageKey}
            index={stageIndex}
            title={stage.title}
            description={stage.description}
            summary={`${stage.missions.length} ${stage.missions.length === 1 ? 'misión' : 'misiones'} · ${taskCount} ${taskCount === 1 ? 'tarea' : 'tareas'}`}
            isOpen={openStages.has(stageKey)}
            onToggle={() => toggleStage(stageKey)}
          >
            <div className="mission-list">
            {[...stage.missions]
              .sort((left, right) => left.order_index - right.order_index)
              .map((mission, missionIndex) => (
                <article
                  className="mission-card"
                  key={`${mission.order_index}-${mission.title}`}
                >
                  <div className="mission-card__heading">
                    <div>
                      <span className="mission-card__index">Misión {missionIndex + 1}</span>
                      <h3>{mission.title}</h3>
                      {mission.description && <p>{mission.description}</p>}
                    </div>
                    {mission.estimated_difficulty && (
                      <span className={`badge badge--${mission.estimated_difficulty}`}>
                        {difficultyLabels[mission.estimated_difficulty]}
                      </span>
                    )}
                  </div>

                  <ol className="task-list">
                    {[...mission.tasks]
                      .sort((left, right) => left.order_index - right.order_index)
                      .map((task) => (
                        <li className="task-row" key={`${task.order_index}-${task.title}`}>
                          <span className="task-row__marker" aria-hidden="true" />
                          <div className="task-row__content">
                            <strong>{task.title}</strong>
                            {task.description && <p>{task.description}</p>}
                          </div>
                          <div className="task-row__metadata">
                            {task.estimated_duration_minutes && (
                              <span>{task.estimated_duration_minutes} min</span>
                            )}
                            <span>{task.xp_reward} XP</span>
                          </div>
                        </li>
                      ))}
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
