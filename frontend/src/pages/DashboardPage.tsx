import {
  useEffect,
  useMemo,
  useState,
} from 'react'
import {
  Link,
} from 'react-router'

import {
  apiRequest,
} from '../lib/api'
import {
  BriefDetailPanel,
} from '../components/BriefDetailPanel'
import {
  isControlledBrief,
} from '../lib/briefs'
import type {
  Brief,
  Competitor,
} from '../lib/types'

function formatDate(value: string) {
  return new Intl.DateTimeFormat(
    undefined,
    {
      dateStyle: 'medium',
      timeStyle: 'short',
    },
  ).format(new Date(value))
}

export function DashboardPage() {
  const [competitors, setCompetitors] =
    useState<Competitor[]>([])
  const [briefs, setBriefs] =
    useState<Brief[]>([])
  const [loading, setLoading] =
    useState(true)
  const [error, setError] =
    useState<string | null>(null)
  const [signalFilter, setSignalFilter] =
    useState('all')
  const [
    selectedBrief,
    setSelectedBrief,
  ] = useState<string | null>(null)

  useEffect(() => {
    let active = true

    async function loadDashboard() {
      try {
        const [
          competitorRows,
          briefRows,
        ] = await Promise.all([
          apiRequest<Competitor[]>(
            '/competitors/',
          ),
          apiRequest<Brief[]>(
            '/briefs/?limit=100',
          ),
        ])

        if (!active) {
          return
        }

        setCompetitors(competitorRows)
        setBriefs(briefRows)
      } catch (requestError) {
        if (!active) {
          return
        }

        setError(
          requestError instanceof Error
            ? requestError.message
            : 'Dashboard could not be loaded',
        )
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }

    void loadDashboard()

    return () => {
      active = false
    }
  }, [])

  const competitorNames = useMemo(
    () =>
      new Map(
        competitors.map((competitor) => [
          competitor.id,
          competitor.name,
        ]),
      ),
    [competitors],
  )

  const filteredBriefs = useMemo(
    () =>
      signalFilter === 'all'
        ? briefs
        : briefs.filter(
            (brief) =>
              brief.signal_type ===
              signalFilter,
          ),
    [briefs, signalFilter],
  )

  const highPriority = briefs.filter(
    (brief) =>
      brief.priority === 'high' ||
      brief.priority === 'urgent',
  ).length

  const undelivered = briefs.filter(
    (brief) => !brief.delivered,
  ).length

  if (loading) {
    return (
      <main className="workspace-state">
        <p className="eyebrow">
          INTELLIGENCE STREAM
        </p>
        <h1>
          Loading market evidence.
        </h1>
        <div className="status-track">
          <span />
        </div>
      </main>
    )
  }

  if (error) {
    return (
      <main className="workspace-state">
        <p className="eyebrow">
          API UNAVAILABLE
        </p>
        <h1>
          Intelligence could not be loaded.
        </h1>
        <p>{error}</p>
        <button
          className="button button--primary"
          type="button"
          onClick={() => {
            window.location.reload()
          }}
        >
          Retry connection
        </button>
      </main>
    )
  }

  return (
    <main className="dashboard">
      <header className="workspace-heading">
        <div>
          <p className="eyebrow">
            LIVE WORKSPACE
          </p>
          <h1>
            Intelligence overview.
          </h1>
        </div>
        <Link
          className="button button--primary"
          to="/onboarding"
        >
          Add competitor
        </Link>
      </header>

      <section
        className="metric-grid"
        aria-label="Workspace metrics"
      >
        <article>
          <span>ACTIVE COMPETITORS</span>
          <strong>
            {String(
              competitors.length,
            ).padStart(2, '0')}
          </strong>
        </article>
        <article>
          <span>AVAILABLE BRIEFS</span>
          <strong>
            {String(
              briefs.length,
            ).padStart(2, '0')}
          </strong>
        </article>
        <article>
          <span>HIGH PRIORITY</span>
          <strong>
            {String(
              highPriority,
            ).padStart(2, '0')}
          </strong>
        </article>
        <article>
          <span>UNDELIVERED</span>
          <strong>
            {String(
              undelivered,
            ).padStart(2, '0')}
          </strong>
        </article>
      </section>

      <div className="dashboard-grid">
        <section className="intelligence-feed">
          <header className="feed-header">
            <div>
              <p className="eyebrow">
                RECENT EVIDENCE
              </p>
              <h2>
                Intelligence stream
              </h2>
            </div>

            <label>
              <span>SIGNAL</span>
              <select
                value={signalFilter}
                onChange={(event) => {
                  setSignalFilter(
                    event.target.value,
                  )
                }}
              >
                <option value="all">
                  All signals
                </option>
                <option value="general">
                  Website
                </option>
                <option value="pricing">
                  Pricing
                </option>
                <option value="reviews">
                  Reviews
                </option>
                <option value="jobs">
                  Hiring
                </option>
                <option value="news">
                  News
                </option>
              </select>
            </label>
          </header>

          {filteredBriefs.length === 0 ? (
            <div className="feed-empty">
              <p className="eyebrow">
                NO BRIEFS YET
              </p>
              <h3>
                No market movement detected.
              </h3>
              <p>
                Monitoring needs two snapshots
                before it can identify a change.
              </p>
            </div>
          ) : (
            <div className="brief-list">
              {filteredBriefs.map(
                (brief) => {
                  const synthesis =
                    brief.synthesis ?? {}
                  const isSelected =
                    selectedBrief === brief.id
                  const controlled =
                    isControlledBrief(brief)

                  return (
                    <article
                      className="brief-row"
                      key={brief.id}
                    >
                      <button
                        type="button"
                        aria-expanded={
                          isSelected
                        }
                        aria-controls={
                          isSelected
                            ? 'brief-detail-panel'
                            : undefined
                        }
                        onClick={() => {
                          setSelectedBrief(brief.id)
                        }}
                      >
                        <span className="brief-signal">
                          {brief.signal_type}
                        </span>
                        <div>
                          <span className="brief-company">
                            {competitorNames.get(
                              brief.competitor_id,
                            ) ??
                              'Competitor'}
                          </span>
                          {controlled && (
                            <span className="brief-test-label">
                              Controlled test
                            </span>
                          )}
                          <h3>
                            {synthesis.headline ??
                              'Competitor change detected'}
                          </h3>
                          <p>
                            {synthesis.summary ??
                              'Open this brief to review the evidence.'}
                          </p>
                        </div>
                        <div className="brief-meta">
                          <span
                            className={
                              `priority priority--${brief.priority}`
                            }
                          >
                            {brief.priority}
                          </span>
                          <time>
                            {formatDate(
                              brief.created_at,
                            )}
                          </time>
                          <i>
                            +
                          </i>
                        </div>
                      </button>
                    </article>
                  )
                },
              )}
            </div>
          )}
        </section>

        <aside className="monitoring-rail">
          <header>
            <p className="eyebrow">
              MONITORED SET
            </p>
            <h2>Competitors</h2>
          </header>

          {competitors.length === 0 ? (
            <div className="rail-empty">
              <p>
                Add your first competitor to
                establish a baseline.
              </p>
              <Link
                className="text-link"
                to="/onboarding"
              >
                Add competitor →
              </Link>
            </div>
          ) : (
            <ol>
              {competitors.map(
                (competitor, index) => (
                  <li key={competitor.id}>
                    <span>
                      {String(index + 1).padStart(
                        2,
                        '0',
                      )}
                    </span>
                    <Link
                      className="competitor-rail-link"
                      to={`/competitors/${competitor.id}`}
                    >
                      <strong>
                        {competitor.name}
                      </strong>
                      <span>
                        {new URL(
                          competitor.website_url,
                        ).hostname}
                      </span>
                    </Link>
                    <i
                      title="Monitoring configured"
                      aria-label="Monitoring configured"
                    />
                  </li>
                ),
              )}
            </ol>
          )}

          <footer>
            <span>
              SYSTEM STATUS
            </span>
            <strong>
              <i aria-hidden="true" />
              OPERATIONAL
            </strong>
          </footer>
        </aside>
      </div>

      {selectedBrief && (() => {
        const brief = briefs.find(
          (item) => item.id === selectedBrief,
        )

        if (!brief) {
          return null
        }

        return (
          <BriefDetailPanel
            brief={brief}
            competitorName={
              competitorNames.get(
                brief.competitor_id,
              ) ?? 'Competitor'
            }
            onClose={() => {
              setSelectedBrief(null)
            }}
          />
        )
      })()}
    </main>
  )
}
