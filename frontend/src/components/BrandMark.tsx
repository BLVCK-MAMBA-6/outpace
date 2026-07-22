import { Link } from 'react-router-dom'

type BrandMarkProps = {
  compact?: boolean
}

export function BrandMark({
  compact = false,
}: BrandMarkProps) {
  return (
    <Link
      className="brand-mark"
      to="/"
      aria-label="Outpace home"
    >
      <span
        className="brand-mark__signal"
        aria-hidden="true"
      />
      <span>
        OUTPACE
      </span>
      {!compact && (
        <span className="brand-mark__edition">
          INTELLIGENCE
        </span>
      )}
    </Link>
  )
}
