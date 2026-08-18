import { Link } from 'react-router-dom'

interface BrandProps {
  linked?: boolean
}

export function Brand({ linked = true }: BrandProps) {
  const content = (
    <>
      <span className="brand__mark" aria-hidden="true">
        <span />
        <span />
        <span />
      </span>
      <span>LevelMind</span>
    </>
  )

  if (!linked) {
    return <div className="brand">{content}</div>
  }

  return (
    <Link className="brand" to="/" aria-label="LevelMind, inicio">
      {content}
    </Link>
  )
}
