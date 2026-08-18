import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { PersistedStage, PlanPreview } from '../types/planning'
import { ActivePlanHierarchy } from './ActivePlanHierarchy'
import { PlanHierarchy } from './PlanHierarchy'

const preview: PlanPreview = {
  stages: [
    {
      title: 'Fundamentos backend',
      description: 'Preparar las bases',
      order_index: 0,
      missions: [
        {
          title: 'Contratos API',
          description: null,
          order_index: 0,
          estimated_difficulty: 'normal',
          tasks: [
            {
              title: 'Definir endpoint',
              description: null,
              order_index: 0,
              estimated_duration_minutes: 30,
              xp_reward: 10,
            },
          ],
        },
      ],
    },
    {
      title: 'Persistencia',
      description: null,
      order_index: 1,
      missions: [
        {
          title: 'Base de datos',
          description: null,
          order_index: 0,
          estimated_difficulty: 'difficult',
          tasks: [
            {
              title: 'Crear migración',
              description: null,
              order_index: 0,
              estimated_duration_minutes: 45,
              xp_reward: 15,
            },
          ],
        },
      ],
    },
  ],
}

const timestamp = '2026-08-18T10:00:00Z'
const completedStage: PersistedStage = {
  id: 'completed-stage',
  goal_id: 'goal-id',
  title: 'Etapa completada',
  description: 'Contenido histórico',
  order_index: 0,
  status: 'completed',
  created_at: timestamp,
  updated_at: timestamp,
  missions: [
    {
      id: 'mission-id',
      stage_id: 'completed-stage',
      title: 'Misión terminada',
      description: null,
      order_index: 0,
      estimated_difficulty: 'normal',
      status: 'completed',
      created_at: timestamp,
      updated_at: timestamp,
      tasks: [
        {
          id: 'task-id',
          mission_id: 'mission-id',
          title: 'Tarea terminada',
          description: null,
          order_index: 0,
          estimated_duration_minutes: 20,
          estimated_difficulty: 'normal',
          xp_reward: 5,
          status: 'completed',
          difficulty_feedback: null,
          feedback_text: null,
          resolved_at: timestamp,
          created_at: timestamp,
          updated_at: timestamp,
        },
      ],
    },
  ],
}

describe('collapsible plan stages', () => {
  it('starts preview stages closed and exposes real compact counts', () => {
    render(<PlanHierarchy preview={preview} />)

    const first = screen.getByRole('button', { name: /Fundamentos backend/ })
    const second = screen.getByRole('button', { name: /Persistencia/ })
    expect(first).toHaveAttribute('aria-expanded', 'false')
    expect(second).toHaveAttribute('aria-expanded', 'false')
    expect(screen.getAllByText('1 misión · 1 tarea')).toHaveLength(2)
    expect(screen.queryByText('Contratos API')).not.toBeInTheDocument()
    expect(screen.queryByText('Definir endpoint')).not.toBeInTheDocument()
    expect(within(first).getByText('⌄')).toHaveAttribute('data-state', 'closed')
  })

  it('opens and closes independently while allowing multiple open stages', async () => {
    render(<PlanHierarchy preview={preview} />)
    const user = userEvent.setup()
    const first = screen.getByRole('button', { name: /Fundamentos backend/ })
    const second = screen.getByRole('button', { name: /Persistencia/ })

    await user.click(first)
    expect(first).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('Contratos API')).toBeInTheDocument()
    expect(within(first).getByText('⌄')).toHaveAttribute('data-state', 'open')

    await user.click(second)
    expect(first).toHaveAttribute('aria-expanded', 'true')
    expect(second).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('Base de datos')).toBeInTheDocument()

    await user.click(first)
    expect(first).toHaveAttribute('aria-expanded', 'false')
    expect(second).toHaveAttribute('aria-expanded', 'true')
    expect(screen.queryByText('Contratos API')).not.toBeInTheDocument()
  })

  it('keeps an active stage open when refreshed data changes', async () => {
    const { rerender } = render(
      <ActivePlanHierarchy
        stages={[completedStage]}
        selectedTaskId={null}
        onSelectTask={vi.fn()}
        renderResolutionPanel={() => null}
      />,
    )
    const user = userEvent.setup()
    const toggle = screen.getByRole('button', { name: /Etapa completada/ })

    await user.click(toggle)
    expect(screen.getByText('Tarea terminada')).toBeInTheDocument()

    rerender(
      <ActivePlanHierarchy
        stages={[{ ...completedStage, updated_at: '2026-08-18T11:00:00Z' }]}
        selectedTaskId={null}
        onSelectTask={vi.fn()}
        renderResolutionPanel={() => null}
      />,
    )
    expect(screen.getByRole('button', { name: /Etapa completada/ })).toHaveAttribute(
      'aria-expanded',
      'true',
    )
    expect(screen.getByText('Tarea terminada')).toBeInTheDocument()
  })

  it('allows a completed stage to expand', async () => {
    render(
      <ActivePlanHierarchy
        stages={[completedStage]}
        selectedTaskId={null}
        onSelectTask={vi.fn()}
        renderResolutionPanel={() => null}
      />,
    )
    const user = userEvent.setup()
    const toggle = screen.getByRole('button', { name: /Etapa completada/ })

    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText('Misión terminada')).not.toBeInTheDocument()
    await user.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('Misión terminada')).toBeInTheDocument()
  })
})
