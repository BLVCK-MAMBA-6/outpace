import {
  useEffect,
  useMemo,
  useState,
} from 'react'
import {
  Link,
  useParams,
} from 'react-router-dom'

import '../styles/source-health.css'

import {
  BriefDetailPanel,
} from '../components/BriefDetailPanel'
import {
  apiRequest,
} from '../lib/api'
import {
  isControlledBrief,
} from '../lib/briefs'
import type {
  Brief,
  CompetitorMonitoring,
  MonitoringSignalStatus,
  SignalType,
  TaskQueued,
  TaskStatus,
} from '../lib/types'

const signalDetails: Record<
  SignalType,
  {
    index: string
    label: string
    description: string
  }
> = {
  general: {
    index: '01',
    label: 'Website',
    description: 'Positioning and product messaging',
  },
  pricing: {
    index: '02',
    label: 'Pricing',
    description: 'Plans, packaging, and feature movement',
  },
  reviews: {
    index: '03',
    label: 'Reviews',
    description: 'Sentiment and rating movement',
  },
  jobs: {
    index: '04',
    label: 'Hiring',
    description: 'Roles, teams, and expansion direction',
  },
  news: {
    index: '05',
    label: 'News',
    description: 'Announcements and market narrative',
  },
}

const healthLabels = {
  unconfigured: 'Needs source',
  disabled: 'Disabled',
  pending: 'Awaiting baseline',
  healthy: 'Healthy',
  degraded: 'Degraded',
  blocked: 'Access blocked',
  unsupported: 'Unsupported',
  failed: 'Check failed',
} as const

type TaskFeedback = {
  state: 'running' | 'success' | 'error'
  message: string
}

function formatDate(value: string | null) {
  if (!value) {
    return 'No collection yet'
  }

  return new Intl.DateTimeFormat(
    undefined,
    {
      dateStyle: 'medium',
      timeStyle: 'short',
    },
  ).format(new Date(value))
}

function wait(milliseconds: number) {
  return new Promise<void>((resolve) => {
    window.setTimeout(resolve, milliseconds)
  })
}

async function waitForTask(taskId: string) {
  for (let attempt = 0; attempt < 45; attempt += 1) {
    const status = await apiRequest<TaskStatus>(
      `/pipeline/tasks/${taskId}`,
    )

    if (status.ready) {
      return status
    }

    await wait(1500)
  }

  throw new Error(
    'Monitoring is still running. Check again shortly.',
  )
}

export function CompetitorDetailPage() {
  const { competitorId } = useParams()
  const [monitoring, setMonitoring] =
    useState<CompetitorMonitoring | null>(null)
  const [briefs, setBriefs] =
    useState<Brief[]>([])
  const [loading, setLoading] =
    useState(true)
  const [error, setError] =
    useState<string | null>(null)
  const [refreshKey, setRefreshKey] =
    useState(0)
  const [selectedBrief, setSelectedBrief] =
    useState<string | null>(null)
  const [taskFeedback, setTaskFeedback] =
    useState<Partial<Record<SignalType, TaskFeedback>>>(
      {},
    )

  useEffect(() => {
    let active = true

    async function loadCompetitor() {
      if (!competitorId) {
        setError('Competitor ID is missing')
        setLoading(false)
        return
      }

      setError(null)

      try {
        const [monitoringState, briefRows] =
          await Promise.all([
            apiRequest<CompetitorMonitoring>(
              `/competitors/${competitorId}/monitoring`,
            ),
            apiRequest<Brief[]>('/briefs/?limit=100'),
          ])

        if (!active) {
          return
        }

        setMonitoring(monitoringState)
        setBriefs(
          briefRows.filter(
            (brief) =>
              brief.competitor_id === competitorId,
          ),
        )
      } catch (requestError) {
        if (!active) {
          return
        }

        setError(
          requestError instanceof Error
            ? requestError.message
            : 'Competitor could not be loaded',
        )
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }

    void loadCompetitor()

    return () => {
      active = false
    }
  }, [competitorId, refreshKey])

  const latestBriefs = useMemo(() => {
    const bySignal = new Map<SignalType, Brief>()

    for (const brief of briefs) {
      const signalType = brief.signal_type as SignalType

      if (!bySignal.has(signalType)) {
        bySignal.set(signalType, brief)
      }
    }

    return bySignal
  }, [briefs])

  async function runMonitoring(
    signal: MonitoringSignalStatus,
  ) {
    if (!competitorId) {
      return
    }

    setTaskFeedback((current) => ({
      ...current,
      [signal.signal_type]: {
        state: 'running',
        message: 'Collecting a fresh snapshot…',
      },
    }))

    try {
      const payload =
        signal.signal_type === 'general' ||
        signal.signal_type === 'pricing'
          ? {
              signal_type: signal.signal_type,
              competitor_id: competitorId,
            }
          : {
              signal_type: signal.signal_type,
              source_id: signal.source_id,
            }

      const queued = await apiRequest<TaskQueued>(
        '/pipeline/enqueue',
        {
          method: 'POST',
          body: JSON.stringify(payload),
        },
      )
      const completed = await waitForTask(
        queued.task_id,
      )

      if (!completed.successful) {
        throw new Error(
          completed.error ?? 'Monitoring task failed',
        )
      }

      setTaskFeedback((current) => ({
        ...current,
        [signal.signal_type]: {
          state: 'success',
          message: 'Collection completed',
        },
      }))
      setRefreshKey((current) => current + 1)
    } catch (requestError) {
      setTaskFeedback((current) => ({
        ...current,
        [signal.signal_type]: {
          state: 'error',
          message:
            requestError instanceof Error
              ? requestError.message
              : 'Monitoring could not be started',
        },
      }))
      setRefreshKey((current) => current + 1)
    }
  }

  if (loading) {
    return (
      <main className="workspace-state">
        <p className="eyebrow">COMPETITOR FILE</p>
        <h1>Loading monitoring record.</h1>
        <div className="status-track">
          <span />
        </div>
      </main>
    )
  }

  if (error || !monitoring) {
    return (
      <main className="workspace-state">
        <p className="eyebrow">RECORD UNAVAILABLE</p>
        <h1>Competitor could not be loaded.</h1>
        <p>{error}</p>
        <Link
          className="button button--primary"
          to="/dashboard"
        >
          Return to overview
        </Link>
      </main>
    )
  }

  const { competitor, signals } = monitoring
  const liveSignalCount = signals.filter(
    (signal) =>
      signal.configured &&
      signal.enabled &&
      signal.provider !== 'manual',
  ).length
  const latestSnapshot = signals
    .map((signal) => signal.latest_snapshot_at)
    .filter((value): value is string => Boolean(value))
    .sort()
    .at(-1) ?? null
  const openBrief = briefs.find(
    (brief) => brief.id === selectedBrief,
  )

  return (
    <main className="competitor-page">
      <header className="competitor-hero">
        <div className="competitor-hero__back">
          <Link to="/dashboard">
            ← Intelligence overview
          </Link>
          <span>
            {liveSignalCount}/5 SIGNALS LIVE
          </span>
        </div>

        <div className="competitor-hero__title">
          <div>
            <p className="eyebrow">COMPETITOR FILE</p>
            <h1>{competitor.name}</h1>
          </div>
          <div className="competitor-hero__links">
            <a
              href={competitor.website_url}
              target="_blank"
              rel="noreferrer"
            >
              Visit website ↗
            </a>
            {competitor.pricing_url && (
              <a
                href={competitor.pricing_url}
                target="_blank"
                rel="noreferrer"
              >
                View pricing ↗
              </a>
            )}
          </div>
        </div>

        <dl className="competitor-facts">
          <div>
            <dt>ACTIVE SIGNALS</dt>
            <dd>{String(liveSignalCount).padStart(2, '0')}</dd>
          </div>
          <div>
            <dt>INTELLIGENCE BRIEFS</dt>
            <dd>{String(briefs.length).padStart(2, '0')}</dd>
          </div>
          <div>
            <dt>LAST COLLECTION</dt>
            <dd className="competitor-facts__date">
              {formatDate(latestSnapshot)}
            </dd>
          </div>
        </dl>
      </header>

      <section className="signal-control-section">
        <header>
          <div>
            <p className="eyebrow">MONITORING SURFACES</p>
            <h2>Five views of movement.</h2>
          </div>
          <p>
            Run an individual check or review the latest
            evidence collected from each source.
          </p>
        </header>

        <div className="signal-control-list">
          {signals.map((signal) => {
            const details = signalDetails[signal.signal_type]
            const latestBrief = latestBriefs.get(
              signal.signal_type,
            )
            const feedback = taskFeedback[signal.signal_type]
            const fixture = signal.provider === 'manual'
            const runnable =
              signal.configured &&
              signal.enabled &&
              !fixture
            const healthClass = fixture
              ? 'fixture'
              : signal.health_status

            return (
              <article
                className="signal-control-row"
                key={signal.signal_type}
              >
                <span className="signal-control-row__index">
                  {details.index}
                </span>

                <div className="signal-control-row__identity">
                  <p className="eyebrow">
                    {signal.provider?.replaceAll('_', ' ') ??
                      'SOURCE REQUIRED'}
                  </p>
                  <h3>{details.label}</h3>
                  <p>{details.description}</p>
                </div>

                <div className="signal-control-row__status">
                  <span
                    className={`signal-state signal-state--${healthClass}`}
                  >
                    {fixture
                      ? 'Test fixture'
                      : healthLabels[signal.health_status]}
                  </span>
                  <p>
                    Latest snapshot
                    <strong>
                      {formatDate(signal.latest_snapshot_at)}
                    </strong>
                  </p>
                  {signal.last_error_message &&
                    signal.health_status !== 'healthy' && (
                      <p
                        className="source-health-error"
                        title={signal.last_error_message}
                      >
                        {signal.last_error_message}
                      </p>
                    )}
                  {signal.consecutive_failures > 0 && (
                    <small className="source-health-failures">
                      {signal.consecutive_failures}{' '}
                      consecutive failure
                      {signal.consecutive_failures === 1
                        ? ''
                        : 's'}
                    </small>
                  )}
                </div>

                <div className="signal-control-row__brief">
                  <span>LATEST INTELLIGENCE</span>
                  {latestBrief ? (
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedBrief(latestBrief.id)
                      }}
                    >
                      {latestBrief.synthesis.headline ??
                        'Open latest brief'}
                      {isControlledBrief(latestBrief) && (
                        <i>Controlled test</i>
                      )}
                    </button>
                  ) : (
                    <p>No brief produced yet</p>
                  )}
                </div>

                <div className="signal-control-row__action">
                  <button
                    className="button button--secondary"
                    type="button"
                    disabled={
                      !runnable ||
                      feedback?.state === 'running'
                    }
                    onClick={() => {
                      void runMonitoring(signal)
                    }}
                  >
                    {feedback?.state === 'running'
                      ? 'Checking…'
                      : fixture
                        ? 'Fixture only'
                        : runnable
                          ? 'Run check'
                          : 'Needs setup'}
                  </button>
                  {feedback && (
                    <p
                      className={
                        `task-feedback task-feedback--${feedback.state}`
                      }
                      role={
                        feedback.state === 'error'
                          ? 'alert'
                          : 'status'
                      }
                    >
                      {feedback.message}
                    </p>
                  )}
                </div>
              </article>
            )
          })}
        </div>
      </section>

      <section className="competitor-history">
        <header>
          <div>
            <p className="eyebrow">DECISION HISTORY</p>
            <h2>Intelligence record</h2>
          </div>
          <span>{briefs.length} briefs</span>
        </header>

        {briefs.length === 0 ? (
          <div className="competitor-history__empty">
            <h3>No decisions recorded yet.</h3>
            <p>
              A brief appears when two snapshots contain a
              meaningful difference.
            </p>
          </div>
        ) : (
          <ol>
            {briefs.map((brief, index) => (
              <li key={brief.id}>
                <span>
                  {String(index + 1).padStart(2, '0')}
                </span>
                <div>
                  <p className="eyebrow">
                    {signalDetails[
                      brief.signal_type as SignalType
                    ]?.label ?? brief.signal_type}
                  </p>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedBrief(brief.id)
                    }}
                  >
                    {brief.synthesis.headline ??
                      'Competitor change detected'}
                  </button>
                </div>
                <div>
                  {isControlledBrief(brief) && (
                    <span className="brief-test-label">
                      Controlled test
                    </span>
                  )}
                  <time>{formatDate(brief.created_at)}</time>
                </div>
              </li>
            ))}
          </ol>
        )}
      </section>

      {openBrief && (
        <BriefDetailPanel
          brief={openBrief}
          competitorName={competitor.name}
          onClose={() => {
            setSelectedBrief(null)
          }}
        />
      )}
    </main>
  )
}
