import type { AdaptationChange, ProposedTask } from '../types/adaptation'

const difficultyLabels = {
  easy: 'Fácil',
  normal: 'Normal',
  difficult: 'Difícil',
} as const

const changeLabels: Record<AdaptationChange['type'], string> = {
  add_task: 'Agregar tarea',
  split_task: 'Dividir tarea',
  replace_task: 'Reemplazar tarea',
  reorder_task: 'Reordenar tarea',
  adjust_task_difficulty: 'Ajustar dificultad',
  adjust_task_duration: 'Ajustar duración',
}

export function AdaptationChangeList({ changes }: { changes: AdaptationChange[] }) {
  return (
    <ol className="adaptation-change-list">
      {changes.map((change, index) => (
        <li className="adaptation-change" key={`${change.type}-${index}`}>
          <header className="adaptation-change__header">
            <span className="adaptation-change__number">{index + 1}</span>
            <div>
              <span className="adaptation-change__badge">{changeLabels[change.type]}</span>
              <p>{change.target.stage_title} · {change.target.mission_title}</p>
            </div>
          </header>
          <ChangeDetails change={change} />
          <p className="adaptation-change__reason">{change.reason}</p>
        </li>
      ))}
    </ol>
  )
}

function ChangeDetails({ change }: { change: AdaptationChange }) {
  switch (change.type) {
    case 'add_task':
      return (
        <div className="adaptation-change__body">
          <span className="change-label">Nueva tarea</span>
          <ProposedTaskDetails task={change.task} />
          <p className="change-position">
            {change.insert_after_task_order_index === null
              ? 'Se ubicará al inicio de la misión.'
              : `Se ubicará después de la tarea ${change.insert_after_task_order_index + 1}.`}
          </p>
        </div>
      )
    case 'split_task':
      return (
        <div className="adaptation-change__body">
          <ChangeTransition current={change.target.task_title} proposed="Subtareas propuestas" />
          <ul className="proposed-task-list">
            {change.replacement_tasks.map((task, index) => (
              <li key={`${task.title}-${index}`}><ProposedTaskDetails task={task} /></li>
            ))}
          </ul>
        </div>
      )
    case 'replace_task':
      return (
        <div className="adaptation-change__body">
          <ChangeTransition current={change.target.task_title} proposed={change.replacement.title} />
          <ProposedTaskDetails task={change.replacement} showTitle={false} />
        </div>
      )
    case 'reorder_task':
      return (
        <div className="adaptation-change__body">
          <strong>{change.target.task_title}</strong>
          <div className="change-comparison">
            <span>Posición actual: {change.target.task_order_index + 1}</span>
            <span aria-hidden="true">→</span>
            <span>Nueva posición: {change.destination_order_index + 1}</span>
          </div>
        </div>
      )
    case 'adjust_task_difficulty':
      return (
        <div className="adaptation-change__body">
          <strong>{change.target.task_title}</strong>
          <p className="change-proposal-value">
            Dificultad propuesta: {difficultyLabels[change.proposed_difficulty]}
          </p>
        </div>
      )
    case 'adjust_task_duration':
      return (
        <div className="adaptation-change__body">
          <strong>{change.target.task_title}</strong>
          <p className="change-proposal-value">
            Nueva duración estimada: {change.estimated_duration_minutes} min
          </p>
        </div>
      )
  }
}

function ChangeTransition({ current, proposed }: { current: string; proposed: string }) {
  return (
    <div className="change-comparison">
      <div><span>Actual</span><strong>{current}</strong></div>
      <span aria-hidden="true">→</span>
      <div><span>Propuesta</span><strong>{proposed}</strong></div>
    </div>
  )
}

function ProposedTaskDetails({ task, showTitle = true }: { task: ProposedTask; showTitle?: boolean }) {
  return (
    <div className="proposed-task">
      {showTitle && <strong>{task.title}</strong>}
      {task.description && <p>{task.description}</p>}
      <div className="proposed-task__metadata">
        <span>{task.estimated_duration_minutes} min</span>
        <span>{task.xp_reward} XP</span>
      </div>
    </div>
  )
}
