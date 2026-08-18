import type { PlanPreview } from '../types/planning'

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

  return (
    <div className="plan-tree">
      {stages.map((stage, stageIndex) => (
        <section className="stage-card" key={`${stage.order_index}-${stage.title}`}>
          <header className="stage-card__header">
            <span className="stage-card__index">Etapa {stageIndex + 1}</span>
            <div>
              <h2>{stage.title}</h2>
              {stage.description && <p>{stage.description}</p>}
            </div>
          </header>

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
        </section>
      ))}
    </div>
  )
}
