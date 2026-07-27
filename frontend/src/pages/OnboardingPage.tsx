import {
  useState,
} from 'react'
import type {
  FormEvent,
} from 'react'
import {
  useNavigate,
} from 'react-router-dom'

import {
  apiRequest,
} from '../lib/api'
import type {
  Competitor,
  CompetitorCreate,
  JobSourceCreate,
  JobSourceDiscovery,
  MonitoringSource,
  NewsSourceCreate,
  SignalType,
  TaskQueued,
} from '../lib/types'

type Step = 1 | 2 | 3

type BaselineTarget = {
  label: string
  signalType: SignalType
  competitorId?: string
  sourceId?: string
}

const jobProviderLabels: Record<
  JobSourceCreate['provider'],
  string
> = {
  html: 'Official careers page',
  github: 'GitHub',
  ashby: 'Ashby',
  greenhouse: 'Greenhouse',
  lever: 'Lever',
  deel: 'Deel-hosted careers',
}

export function OnboardingPage() {
  const navigate = useNavigate()

  const [step, setStep] =
    useState<Step>(1)
  const [competitor, setCompetitor] =
    useState<Competitor | null>(null)
  const [name, setName] =
    useState('')
  const [websiteUrl, setWebsiteUrl] =
    useState('')
  const [pricingUrl, setPricingUrl] =
    useState('')

  const [jobsEnabled, setJobsEnabled] =
    useState(false)
  const [jobProvider, setJobProvider] =
    useState<JobSourceCreate['provider']>('html')
  const [jobSourceUrl, setJobSourceUrl] =
    useState('')
  const [jobDiscovery, setJobDiscovery] =
    useState<JobSourceDiscovery | null>(null)
  const [discoveringJobs, setDiscoveringJobs] =
    useState(false)
  const [jobLinkPath, setJobLinkPath] =
    useState('/careers/')
  const [githubBranch, setGithubBranch] =
    useState('main')
  const [githubReadmePath, setGithubReadmePath] =
    useState('README.md')

  const [newsEnabled, setNewsEnabled] =
    useState(false)
  const [newsSourceUrl, setNewsSourceUrl] =
    useState('')
  const [articleLinkPath, setArticleLinkPath] =
    useState('/blog/post/')
  const [newsKeywords, setNewsKeywords] =
    useState(
      'pricing, launch, partnership, acquisition, AI',
    )
  const [maxArticles, setMaxArticles] =
    useState('25')

  const [jobSource, setJobSource] =
    useState<MonitoringSource | null>(null)
  const [newsSource, setNewsSource] =
    useState<MonitoringSource | null>(null)
  const [queuedSignals, setQueuedSignals] =
    useState<SignalType[]>([])
  const [submitting, setSubmitting] =
    useState(false)
  const [error, setError] =
    useState<string | null>(null)

  const stepCopy = {
    1: {
      eyebrow: 'MONITORING SETUP',
      title: 'Establish a competitor baseline.',
    },
    2: {
      eyebrow: 'SOURCE CONFIGURATION',
      title: 'Choose the surfaces worth watching.',
    },
    3: {
      eyebrow: 'BASELINE REVIEW',
      title: 'Put the market into motion.',
    },
  }[step]

  async function handleCompanySubmit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)

    const payload: CompetitorCreate = {
      name: name.trim(),
      website_url: websiteUrl.trim(),
      pricing_url:
        pricingUrl.trim() || null,
    }

    try {
      const created = await apiRequest<Competitor>(
        '/competitors/',
        {
          method: 'POST',
          body: JSON.stringify(payload),
        },
      )

      setCompetitor(created)
      setStep(2)
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Could not add competitor',
      )
    } finally {
      setSubmitting(false)
    }
  }

  async function handleSourceSubmit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault()

    if (!competitor) {
      setError('Create the competitor before adding sources.')
      setStep(1)
      return
    }

    setSubmitting(true)
    setError(null)

    const requests: Promise<void>[] = []

    if (jobsEnabled) {
      if (!jobDiscovery) {
        setSubmitting(false)
        setError(
          'Detect and confirm the careers source before continuing.',
        )
        return
      }

      const payload: JobSourceCreate = {
        provider: jobProvider,
        source_url: jobSourceUrl.trim(),
        ...(jobDiscovery.external_source_id
          ? {
              external_source_id:
                jobDiscovery.external_source_id,
            }
          : {}),
        ...(jobDiscovery.region
          ? { region: jobDiscovery.region }
          : {}),
        ...(jobProvider === 'html'
          ? {
              job_link_path: jobLinkPath.trim(),
            }
          : jobProvider === 'github'
            ? {
                branch: githubBranch.trim(),
                readme_path: githubReadmePath.trim(),
              }
            : {}),
      }

      requests.push(
        apiRequest<MonitoringSource>(
          `/competitors/${competitor.id}/sources/jobs`,
          {
            method: 'POST',
            body: JSON.stringify(payload),
          },
        ).then((stored) => {
          setJobSource(stored)
        }),
      )
    } else {
      setJobSource(null)
    }

    if (newsEnabled) {
      const keywords = newsKeywords
        .split(',')
        .map((keyword) => keyword.trim())
        .filter(Boolean)
      const payload: NewsSourceCreate = {
        provider: 'html',
        source_url: newsSourceUrl.trim(),
        article_link_path: articleLinkPath.trim(),
        keywords,
        max_articles: Number(maxArticles),
      }

      requests.push(
        apiRequest<MonitoringSource>(
          `/competitors/${competitor.id}/sources/news`,
          {
            method: 'POST',
            body: JSON.stringify(payload),
          },
        ).then((stored) => {
          setNewsSource(stored)
        }),
      )
    } else {
      setNewsSource(null)
    }

    try {
      const results = await Promise.allSettled(requests)
      const failed = results.find(
        (result) => result.status === 'rejected',
      )

      if (failed?.status === 'rejected') {
        throw failed.reason
      }

      setStep(3)
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Could not save monitoring sources',
      )
    } finally {
      setSubmitting(false)
    }
  }

  async function handleJobDiscovery() {
    if (!competitor) {
      setError('Create the competitor before detecting sources.')
      return
    }

    if (!jobSourceUrl.trim()) {
      setError('Enter the public careers page or job-board URL.')
      return
    }

    setDiscoveringJobs(true)
    setJobDiscovery(null)
    setError(null)

    try {
      const discovered = await apiRequest<JobSourceDiscovery>(
        `/competitors/${competitor.id}/sources/jobs/discover`,
        {
          method: 'POST',
          body: JSON.stringify({
            careers_url: jobSourceUrl.trim(),
          }),
        },
      )

      setJobDiscovery(discovered)
      setJobProvider(discovered.provider)

      const detectedPath = discovered.metadata.job_link_path
      if (typeof detectedPath === 'string') {
        setJobLinkPath(detectedPath)
      }
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Could not verify a supported careers source',
      )
    } finally {
      setDiscoveringJobs(false)
    }
  }

  function getBaselineTargets(): BaselineTarget[] {
    if (!competitor) {
      return []
    }

    const targets: BaselineTarget[] = [
      {
        label: 'Website',
        signalType: 'general',
        competitorId: competitor.id,
      },
    ]

    if (competitor.pricing_url) {
      targets.push({
        label: 'Pricing',
        signalType: 'pricing',
        competitorId: competitor.id,
      })
    }

    if (jobSource) {
      targets.push({
        label: 'Hiring',
        signalType: 'jobs',
        sourceId: jobSource.id,
      })
    }

    if (newsSource) {
      targets.push({
        label: 'News',
        signalType: 'news',
        sourceId: newsSource.id,
      })
    }

    return targets
  }

  async function handleEstablishBaselines() {
    if (!competitor) {
      setError('Competitor setup is incomplete.')
      return
    }

    setSubmitting(true)
    setError(null)

    const remainingTargets = getBaselineTargets().filter(
      (target) => !queuedSignals.includes(target.signalType),
    )

    try {
      const results = await Promise.allSettled(
        remainingTargets.map((target) =>
          apiRequest<TaskQueued>(
            '/pipeline/enqueue',
            {
              method: 'POST',
              body: JSON.stringify({
                signal_type: target.signalType,
                competitor_id: target.competitorId,
                source_id: target.sourceId,
              }),
            },
          ),
        ),
      )
      const newlyQueued = remainingTargets
        .filter((_, index) =>
          results[index].status === 'fulfilled',
        )
        .map((target) => target.signalType)
      const allQueued = [
        ...new Set([
          ...queuedSignals,
          ...newlyQueued,
        ]),
      ]
      const failures = results.filter(
        (result) => result.status === 'rejected',
      )

      setQueuedSignals(allQueued)

      if (failures.length > 0) {
        setError(
          `${newlyQueued.length} baseline${
            newlyQueued.length === 1 ? '' : 's'
          } queued. ${failures.length} could not be started; retry to finish.`,
        )
        return
      }

      navigate(
        `/competitors/${competitor.id}`,
        {
          replace: true,
        },
      )
    } finally {
      setSubmitting(false)
    }
  }

  const baselineTargets = getBaselineTargets()

  return (
    <main className="onboarding-page onboarding-page--complete">
      <header className="workspace-heading onboarding-heading">
        <div>
          <p className="eyebrow">
            {stepCopy.eyebrow}
          </p>
          <h1>{stepCopy.title}</h1>
        </div>
        <span>
          STEP 0{step} / 03
        </span>
      </header>

      <div className="onboarding-grid onboarding-grid--complete">
        <aside className="onboarding-steps">
          <ol>
            <li
              className={
                step === 1
                  ? 'active'
                  : step > 1
                    ? 'complete'
                    : ''
              }
            >
              <span>01</span>
              <div>
                <strong>Company</strong>
                <p>
                  {competitor
                    ? competitor.name
                    : 'Core identity and URLs'}
                </p>
              </div>
            </li>
            <li
              className={
                step === 2
                  ? 'active'
                  : step > 2
                    ? 'complete'
                    : ''
              }
            >
              <span>02</span>
              <div>
                <strong>Sources</strong>
                <p>Careers and news coverage</p>
              </div>
            </li>
            <li className={step === 3 ? 'active' : ''}>
              <span>03</span>
              <div>
                <strong>Confirm</strong>
                <p>Queue live baselines</p>
              </div>
            </li>
          </ol>

          <div className="onboarding-assurance">
            <span>LIVE DATA POLICY</span>
            <p>
              Only public, supported sources are connected.
              Synthetic fixtures never appear in onboarding.
            </p>
          </div>
        </aside>

        <section className="onboarding-form-section onboarding-form-section--wide">
          {step === 1 && (
            <>
              <p className="eyebrow">
                COMPETITOR IDENTITY
              </p>
              <h2>Who should Outpace watch?</h2>
              <p className="onboarding-intro">
                Start with the two surfaces every competitor owns.
                Outpace will collect the first snapshot after review.
              </p>

              <form
                className="onboarding-form"
                onSubmit={(event) => {
                  void handleCompanySubmit(event)
                }}
              >
                <label>
                  <span>COMPETITOR NAME</span>
                  <input
                    required
                    value={name}
                    placeholder="Example Analytics"
                    onChange={(event) => {
                      setName(event.target.value)
                    }}
                  />
                </label>

                <label>
                  <span>WEBSITE URL</span>
                  <input
                    required
                    type="url"
                    value={websiteUrl}
                    placeholder="https://example.com"
                    onChange={(event) => {
                      setWebsiteUrl(event.target.value)
                    }}
                  />
                  <small>
                    Used for positioning and homepage monitoring.
                  </small>
                </label>

                <label>
                  <span>PRICING URL / OPTIONAL</span>
                  <input
                    type="url"
                    value={pricingUrl}
                    placeholder="https://example.com/pricing"
                    onChange={(event) => {
                      setPricingUrl(event.target.value)
                    }}
                  />
                  <small>
                    Add this when the competitor publishes pricing.
                  </small>
                </label>

                {error && (
                  <p className="form-error" role="alert">
                    {error}
                  </p>
                )}

                <button
                  className="button button--primary"
                  disabled={submitting}
                  type="submit"
                >
                  {submitting
                    ? 'Creating competitor…'
                    : 'Continue to sources →'}
                </button>
              </form>
            </>
          )}

          {step === 2 && competitor && (
            <>
              <p className="eyebrow">
                OPTIONAL COVERAGE
              </p>
              <h2>Connect official sources.</h2>
              <p className="onboarding-intro">
                Add only the surfaces this competitor publishes.
                You can leave either source off and configure it later.
              </p>

              <form
                className="source-setup-form"
                onSubmit={(event) => {
                  void handleSourceSubmit(event)
                }}
              >
                <article
                  className={`source-setup-card${
                    jobsEnabled ? ' active' : ''
                  }`}
                >
                  <header>
                    <div>
                      <span>HIRING DIRECTION</span>
                      <h3>Careers source</h3>
                      <p>
                        Read public roles, teams, locations, and
                        remote hiring movement.
                      </p>
                    </div>
                    <label className="source-switch">
                      <input
                        type="checkbox"
                        checked={jobsEnabled}
                        onChange={(event) => {
                          const enabled = event.target.checked
                          setJobsEnabled(enabled)
                          if (!enabled) {
                            setJobDiscovery(null)
                          }
                        }}
                      />
                      <span>
                        {jobsEnabled ? 'Included' : 'Optional'}
                      </span>
                    </label>
                  </header>

                  {jobsEnabled && (
                    <div className="source-setup-fields">
                      <label>
                        <span>CAREERS PAGE OR JOB BOARD URL</span>
                        <input
                          required
                          type="url"
                          value={jobSourceUrl}
                          placeholder="https://example.com/careers/"
                          onChange={(event) => {
                            setJobSourceUrl(event.target.value)
                            setJobDiscovery(null)
                          }}
                        />
                        <small>
                          Outpace detects the supported source and asks
                          you to confirm it before saving.
                        </small>
                      </label>

                      <button
                        className="button button--quiet source-detect-button"
                        type="button"
                        disabled={discoveringJobs}
                        onClick={() => {
                          void handleJobDiscovery()
                        }}
                      >
                        {discoveringJobs
                          ? 'DETECTING SOURCE…'
                          : jobDiscovery
                            ? 'DETECT AGAIN'
                            : 'DETECT SOURCE'}
                      </button>

                      {jobDiscovery && (
                        <div
                          className="source-discovery-result"
                          role="status"
                        >
                          <div>
                            <span>VERIFIED SUGGESTION</span>
                            <strong>{jobDiscovery.message}</strong>
                          </div>
                          <dl>
                            <div>
                              <dt>CONFIDENCE</dt>
                              <dd>{jobDiscovery.confidence}</dd>
                            </div>
                            <div>
                              <dt>PUBLISHED ROLES</dt>
                              <dd>
                                {jobDiscovery.job_count
                                  ?? 'Verified on first run'}
                              </dd>
                            </div>
                          </dl>
                          <p>
                            Nothing is connected until you continue.
                            Change the URL to reject this suggestion.
                          </p>
                        </div>
                      )}

                      {jobDiscovery && jobProvider === 'html' ? (
                        <label>
                          <span>JOB URL PATTERN</span>
                          <input
                            required
                            value={jobLinkPath}
                            placeholder="/careers/"
                            onChange={(event) => {
                              setJobLinkPath(event.target.value)
                            }}
                          />
                          <small>
                            The shared path inside each individual job URL.
                          </small>
                        </label>
                      ) : jobDiscovery && jobProvider === 'github' ? (
                        <div className="source-field-pair">
                          <label>
                            <span>BRANCH</span>
                            <input
                              required
                              value={githubBranch}
                              onChange={(event) => {
                                setGithubBranch(event.target.value)
                              }}
                            />
                          </label>
                          <label>
                            <span>LISTING FILE</span>
                            <input
                              required
                              value={githubReadmePath}
                              onChange={(event) => {
                                setGithubReadmePath(event.target.value)
                              }}
                            />
                          </label>
                        </div>
                      ) : null}
                    </div>
                  )}
                </article>

                <article
                  className={`source-setup-card${
                    newsEnabled ? ' active' : ''
                  }`}
                >
                  <header>
                    <div>
                      <span>MARKET NARRATIVE</span>
                      <h3>News and press source</h3>
                      <p>
                        Follow official announcements, launches,
                        partnerships, and strategic language.
                      </p>
                    </div>
                    <label className="source-switch">
                      <input
                        type="checkbox"
                        checked={newsEnabled}
                        onChange={(event) => {
                          setNewsEnabled(event.target.checked)
                        }}
                      />
                      <span>
                        {newsEnabled ? 'Included' : 'Optional'}
                      </span>
                    </label>
                  </header>

                  {newsEnabled && (
                    <div className="source-setup-fields">
                      <label>
                        <span>BLOG OR NEWSROOM URL</span>
                        <input
                          required
                          type="url"
                          value={newsSourceUrl}
                          placeholder="https://example.com/blog"
                          onChange={(event) => {
                            setNewsSourceUrl(event.target.value)
                          }}
                        />
                      </label>
                      <div className="source-field-pair">
                        <label>
                          <span>ARTICLE URL PATTERN</span>
                          <input
                            required
                            value={articleLinkPath}
                            placeholder="/blog/post/"
                            onChange={(event) => {
                              setArticleLinkPath(event.target.value)
                            }}
                          />
                        </label>
                        <label>
                          <span>MAX ARTICLES</span>
                          <input
                            required
                            type="number"
                            min="1"
                            max="100"
                            value={maxArticles}
                            onChange={(event) => {
                              setMaxArticles(event.target.value)
                            }}
                          />
                        </label>
                      </div>
                      <label>
                        <span>KEYWORDS / COMMA SEPARATED</span>
                        <input
                          value={newsKeywords}
                          onChange={(event) => {
                            setNewsKeywords(event.target.value)
                          }}
                        />
                      </label>
                    </div>
                  )}
                </article>

                <article className="source-setup-card source-setup-card--locked">
                  <header>
                    <div>
                      <span>CUSTOMER SENTIMENT</span>
                      <h3>Review provider</h3>
                      <p>
                        Live G2 access is awaiting provider data
                        entitlement. No synthetic reviews will be connected.
                      </p>
                    </div>
                    <span className="source-lock-state">
                      NOT YET AVAILABLE
                    </span>
                  </header>
                </article>

                {error && (
                  <p className="form-error" role="alert">
                    {error}
                  </p>
                )}

                <div className="onboarding-actions">
                  <button
                    className="button button--quiet"
                    type="button"
                    onClick={() => {
                      setJobsEnabled(false)
                      setNewsEnabled(false)
                      setJobSource(null)
                      setNewsSource(null)
                      setError(null)
                      setStep(3)
                    }}
                  >
                    Skip optional sources
                  </button>
                  <button
                    className="button button--primary"
                    disabled={submitting}
                    type="submit"
                  >
                    {submitting
                      ? 'Saving sources…'
                      : 'Review monitoring →'}
                  </button>
                </div>
              </form>
            </>
          )}

          {step === 3 && competitor && (
            <>
              <p className="eyebrow">
                READY TO COLLECT
              </p>
              <h2>Your live coverage plan.</h2>
              <p className="onboarding-intro">
                Outpace will queue the first collection for every
                configured signal. The first snapshot establishes a
                baseline; later snapshots reveal movement.
              </p>

              <div className="baseline-review">
                <header>
                  <div>
                    <span>COMPETITOR</span>
                    <strong>{competitor.name}</strong>
                  </div>
                  <a
                    href={competitor.website_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {new URL(competitor.website_url).hostname}
                  </a>
                </header>

                <ul>
                  {baselineTargets.map((target, index) => (
                    <li key={target.signalType}>
                      <span>
                        {String(index + 1).padStart(2, '0')}
                      </span>
                      <div>
                        <strong>{target.label}</strong>
                        <p>
                          {target.signalType === 'general' &&
                            'Homepage positioning and product movement'}
                          {target.signalType === 'pricing' &&
                            'Plans, packaging, prices, and features'}
                          {target.signalType === 'jobs' &&
                            `${
                              jobProviderLabels[
                                jobSource?.provider as
                                  JobSourceCreate['provider']
                              ] ?? 'Official careers page'
                            } source`}
                          {target.signalType === 'news' &&
                            'Official blog or newsroom source'}
                        </p>
                      </div>
                      <em>
                        {queuedSignals.includes(target.signalType)
                          ? 'QUEUED'
                          : 'READY'}
                      </em>
                    </li>
                  ))}
                </ul>

                <footer>
                  <span>REVIEWS</span>
                  <p>
                    Deferred until a permitted live provider is available.
                  </p>
                </footer>
              </div>

              {error && (
                <p className="form-error" role="alert">
                  {error}
                </p>
              )}

              <div className="onboarding-actions">
                <button
                  className="button button--quiet"
                  type="button"
                  disabled={submitting}
                  onClick={() => {
                    setError(null)
                    setStep(2)
                  }}
                >
                  ← Adjust sources
                </button>
                <button
                  className="button button--primary"
                  type="button"
                  disabled={submitting}
                  onClick={() => {
                    void handleEstablishBaselines()
                  }}
                >
                  {submitting
                    ? 'Queueing baselines…'
                    : queuedSignals.length > 0
                      ? 'Retry remaining baselines →'
                      : 'Establish live baselines →'}
                </button>
              </div>
            </>
          )}
        </section>
      </div>
    </main>
  )
}
