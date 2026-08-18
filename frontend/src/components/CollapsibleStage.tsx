import { useId, type ReactNode } from 'react'

interface CollapsibleStageProps {
  children: ReactNode
  className?: string
  description?: string | null
  index: number
  isOpen: boolean
  onToggle: () => void
  status?: ReactNode
  summary: string
  title: string
}

export function CollapsibleStage({
  children,
  className = '',
  description,
  index,
  isOpen,
  onToggle,
  status,
  summary,
  title,
}: CollapsibleStageProps) {
  const contentId = useId()

  return (
    <section className={`stage-card ${className}`.trim()}>
      <h2 className="stage-card__toggle-heading">
        <button
          className="stage-card__toggle"
          type="button"
          aria-controls={contentId}
          aria-expanded={isOpen}
          onClick={onToggle}
        >
          <span className="stage-card__index">Etapa {index + 1}</span>
          <span className="stage-card__heading-content">
            <span className="stage-card__title-row">
              <span className="stage-card__title">{title}</span>
              {status}
            </span>
            {description && <span className="stage-card__description">{description}</span>}
            <span className="stage-card__summary">{summary}</span>
          </span>
          <span
            className="stage-card__chevron"
            data-state={isOpen ? 'open' : 'closed'}
            aria-hidden="true"
          >
            ⌄
          </span>
        </button>
      </h2>

      {isOpen && (
        <div className="stage-card__content" id={contentId}>
          {children}
        </div>
      )}
    </section>
  )
}
