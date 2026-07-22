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
} from '../lib/types'

export function OnboardingPage() {
  const navigate = useNavigate()

  const [name, setName] =
    useState('')
  const [websiteUrl, setWebsiteUrl] =
    useState('')
  const [pricingUrl, setPricingUrl] =
    useState('')
  const [submitting, setSubmitting] =
    useState(false)
  const [error, setError] =
    useState<string | null>(null)

  async function handleSubmit(
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
      await apiRequest<Competitor>(
        '/competitors/',
        {
          method: 'POST',
          body: JSON.stringify(payload),
        },
      )

      navigate('/dashboard', {
        replace: true,
      })
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

  return (
    <main className="onboarding-page">
      <header className="workspace-heading">
        <div>
          <p className="eyebrow">
            MONITORING SETUP
          </p>
          <h1>
            Establish a competitor baseline.
          </h1>
        </div>
        <span>
          STEP 01 / 03
        </span>
      </header>

      <div className="onboarding-grid">
        <aside className="onboarding-steps">
          <ol>
            <li className="active">
              <span>01</span>
              <div>
                <strong>Company</strong>
                <p>Core identity and URLs</p>
              </div>
            </li>
            <li>
              <span>02</span>
              <div>
                <strong>Sources</strong>
                <p>Source setup coming next</p>
              </div>
            </li>
            <li>
              <span>03</span>
              <div>
                <strong>Confirm</strong>
                <p>Establish monitoring</p>
              </div>
            </li>
          </ol>
        </aside>

        <section className="onboarding-form-section">
          <p className="eyebrow">
            COMPETITOR IDENTITY
          </p>
          <h2>
            Who should Outpace watch?
          </h2>

          <form
            className="onboarding-form"
            onSubmit={(event) => {
              void handleSubmit(event)
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
                  setWebsiteUrl(
                    event.target.value,
                  )
                }}
              />
            </label>

            <label>
              <span>
                PRICING URL / OPTIONAL
              </span>
              <input
                type="url"
                value={pricingUrl}
                placeholder="https://example.com/pricing"
                onChange={(event) => {
                  setPricingUrl(
                    event.target.value,
                  )
                }}
              />
            </label>

            {error && (
              <p
                className="form-error"
                role="alert"
              >
                {error}
              </p>
            )}

            <button
              className="button button--primary"
              disabled={submitting}
              type="submit"
            >
              {submitting
                ? 'Creating baseline…'
                : 'Add competitor →'}
            </button>
          </form>

          <div className="source-preview">
            <span>
              SOURCE SETUP / COMING NEXT
            </span>
            <p>
              Reviews, careers, and news
              sources require dedicated
              configuration endpoints and
              are not faked in this interface.
            </p>
          </div>
        </section>
      </div>
    </main>
  )
}
