import {
  useEffect,
  useRef,
} from 'react'

import type {
  Brief,
} from '../lib/types'
import {
  isControlledBrief,
} from '../lib/briefs'

const signalNames: Record<string, string> = {
  general: 'Website',
  pricing: 'Pricing',
  reviews: 'Reviews',
  jobs: 'Hiring',
  news: 'News',
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(
    undefined,
    {
      dateStyle: 'long',
      timeStyle: 'short',
    },
  ).format(new Date(value))
}

type BriefDetailPanelProps = {
  brief: Brief
  competitorName: string
  onClose: () => void
}

export function BriefDetailPanel({
  brief,
  competitorName,
  onClose,
}: BriefDetailPanelProps) {
  const closeButtonRef =
    useRef<HTMLButtonElement>(null)
  const synthesis = brief.synthesis ?? {}
  const controlled = isControlledBrief(brief)
  const evidence = Array.isArray(
    synthesis.evidence,
  )
    ? synthesis.evidence
    : []
  const confidence =
    typeof synthesis.confidence === 'number'
      ? `${Math.round(synthesis.confidence * 100)}%`
      : 'Not scored'

  useEffect(() => {
    const previousFocus =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null
    const previousOverflow =
      document.body.style.overflow

    document.body.style.overflow = 'hidden'
    closeButtonRef.current?.focus()

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        onClose()
      }

      if (event.key === 'Tab') {
        event.preventDefault()
        closeButtonRef.current?.focus()
      }
    }

    window.addEventListener(
      'keydown',
      handleKeyDown,
    )

    return () => {
      document.body.style.overflow =
        previousOverflow
      window.removeEventListener(
        'keydown',
        handleKeyDown,
      )
      previousFocus?.focus()
    }
  }, [onClose])

  return (
    <div
      className="brief-drawer-shell"
      role="presentation"
    >
      <button
        className="brief-drawer-backdrop"
        type="button"
        aria-label="Close intelligence brief"
        onClick={onClose}
      />

      <aside
        className="brief-drawer"
        id="brief-detail-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="brief-drawer-title"
      >
        <header className="brief-drawer__header">
          <div>
            <p className="eyebrow">
              INTELLIGENCE BRIEF
            </p>
            <strong>{competitorName}</strong>
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            aria-label="Close intelligence brief"
            onClick={onClose}
          >
            <span aria-hidden="true">Close</span>
            <i aria-hidden="true">×</i>
          </button>
        </header>

        <div className="brief-drawer__meta">
          <span>
            {signalNames[brief.signal_type] ??
              brief.signal_type}
          </span>
          <span
            className={
              `priority priority--${brief.priority}`
            }
          >
            {brief.priority} priority
          </span>
          <time>
            {formatDate(brief.created_at)}
          </time>
        </div>

        {controlled && (
          <div
            className="brief-test-notice"
            role="note"
          >
            <strong>Controlled test data</strong>
            <p>
              This brief validates the monitoring
              pipeline. It is not a verified market
              event.
            </p>
          </div>
        )}

        <section className="brief-drawer__lead">
          <p className="eyebrow">
            DECISION SIGNAL
          </p>
          <h2 id="brief-drawer-title">
            {synthesis.headline ??
              'Competitor change detected'}
          </h2>
          <p>
            {synthesis.summary ??
              'No summary was stored for this brief.'}
          </p>
        </section>

        <div className="brief-drawer__decision-grid">
          <section>
            <p className="eyebrow">
              WHY IT MATTERS
            </p>
            <p>
              {synthesis.why_it_matters ??
                'No significance statement was provided.'}
            </p>
          </section>
          <section>
            <p className="eyebrow">
              RECOMMENDED ACTION
            </p>
            <p>
              {synthesis.recommended_action ??
                'No action was provided.'}
            </p>
          </section>
        </div>

        <section className="brief-drawer__evidence">
          <header>
            <div>
              <p className="eyebrow">
                SOURCE EVIDENCE
              </p>
              <h3>Receipts behind the signal</h3>
            </div>
            <span>
              {String(evidence.length).padStart(
                2,
                '0',
              )}{' '}
              lines
            </span>
          </header>

          {evidence.length > 0 ? (
            <ol>
              {evidence.map((item, index) => (
                <li key={`${index}-${item}`}>
                  <span>
                    {String(index + 1).padStart(
                      2,
                      '0',
                    )}
                  </span>
                  <p>{item}</p>
                </li>
              ))}
            </ol>
          ) : (
            <p className="brief-drawer__empty">
              No evidence lines were stored.
            </p>
          )}
        </section>

        <footer className="brief-drawer__footer">
          <div>
            <span>CONFIDENCE</span>
            <strong>{confidence}</strong>
          </div>
          <div>
            <span>DELIVERY</span>
            <strong>
              {brief.delivered
                ? 'Delivered'
                : 'Awaiting digest'}
            </strong>
          </div>
          <div>
            <span>BRIEF ID</span>
            <strong>{brief.id.slice(0, 8)}</strong>
          </div>
        </footer>
      </aside>
    </div>
  )
}
