import { Link } from 'react-router'

import { BrandMark } from '../components/BrandMark'

export function NotFoundPage() {
  return (
    <main className="not-found">
      <BrandMark />
      <p className="eyebrow">
        ERROR / 404
      </p>
      <h1>
        This signal does not exist.
      </h1>
      <Link
        className="button button--primary"
        to="/"
      >
        Return to Outpace
      </Link>
    </main>
  )
}
