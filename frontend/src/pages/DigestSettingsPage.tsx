import {
  useEffect,
  useState,
} from 'react'
import type {
  FormEvent,
} from 'react'

import {
  apiRequest,
} from '../lib/api'

type DigestPreference = {
  user_id: string
  enabled: boolean
  delivery_email: string
  frequency: 'weekly'
  last_sent_at: string | null
  created_at: string | null
  updated_at: string | null
}

function formatDeliveryDate(
  value: string | null,
) {
  if (!value) {
    return 'No digest sent yet'
  }

  return new Intl.DateTimeFormat(
    undefined,
    {
      dateStyle: 'medium',
      timeStyle: 'short',
    },
  ).format(new Date(value))
}

export function DigestSettingsPage() {
  const [
    preference,
    setPreference,
  ] = useState<DigestPreference | null>(null)
  const [loading, setLoading] =
    useState(true)
  const [saving, setSaving] =
    useState(false)
  const [error, setError] =
    useState<string | null>(null)
  const [confirmation, setConfirmation] =
    useState<string | null>(null)

  useEffect(() => {
    let active = true

    async function loadPreference() {
      try {
        const result =
          await apiRequest<DigestPreference>(
            '/digest-preferences/',
          )

        if (!active) {
          return
        }

        setPreference(result)
      } catch (requestError) {
        if (!active) {
          return
        }

        setError(
          requestError instanceof Error
            ? requestError.message
            : (
                'Digest preference could '
                + 'not be loaded'
              ),
        )
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }

    void loadPreference()

    return () => {
      active = false
    }
  }, [])

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault()

    if (!preference) {
      return
    }

    setSaving(true)
    setError(null)
    setConfirmation(null)

    try {
      const updated =
        await apiRequest<DigestPreference>(
          '/digest-preferences/',
          {
            method: 'PATCH',
            body: JSON.stringify({
              enabled: preference.enabled,
            }),
          },
        )

      setPreference(updated)
      setConfirmation(
        updated.enabled
          ? (
              'Weekly digest enabled. '
              + 'New intelligence will be '
              + 'sent to your verified email.'
            )
          : (
              'Weekly digest paused. '
              + 'Your monitoring continues '
              + 'inside Outpace.'
            ),
      )
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : (
              'Digest preference could '
              + 'not be saved'
            ),
      )
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <main className="workspace-state">
        <p className="eyebrow">
          DELIVERY CONTROL
        </p>
        <h1>
          Loading digest preference.
        </h1>
        <div className="status-track">
          <span />
        </div>
      </main>
    )
  }

  if (!preference) {
    return (
      <main className="workspace-state">
        <p className="eyebrow">
          DIGEST UNAVAILABLE
        </p>
        <h1>
          We could not load your email setting.
        </h1>
        <p>
          {error ?? (
            'Please refresh and try again.'
          )}
        </p>
      </main>
    )
  }

  return (
    <main className="digest-settings">
      <header className="digest-settings__intro">
        <p className="eyebrow">
          DELIVERY CONTROL
        </p>
        <h1>
          Your weekly intelligence,
          <span className="accent">
            {' '}on your terms.
          </span>
        </h1>
        <p>
          Receive one private summary of new
          competitor briefs from your Outpace
          workspace. Nothing is sent when there
          is no new intelligence.
        </p>
      </header>

      <div className="digest-settings__panel">
        <section
          className="digest-settings__summary"
          aria-labelledby="digest-summary-title"
        >
          <p className="eyebrow">
            CURRENT DELIVERY
          </p>
          <h2 id="digest-summary-title">
            Weekly competitive brief
          </h2>

          <dl className="digest-settings__meta">
            <div>
              <dt>Delivery address</dt>
              <dd>
                {preference.delivery_email}
              </dd>
              <small>
                Verified through your Outpace
                sign-in.
              </small>
            </div>

            <div>
              <dt>Cadence</dt>
              <dd>Weekly</dd>
              <small>
                New, undelivered briefs only.
              </small>
            </div>

            <div>
              <dt>Last delivered</dt>
              <dd>
                {formatDeliveryDate(
                  preference.last_sent_at,
                )}
              </dd>
            </div>
          </dl>
        </section>

        <form
          className="digest-settings__form"
          onSubmit={(event) => {
            void handleSubmit(event)
          }}
        >
          <div>
            <p className="eyebrow">
              EMAIL PREFERENCE
            </p>
            <h2>
              Keep me in the loop
            </h2>
            <p>
              Outpace will combine your own
              website, pricing, review, hiring,
              and news briefs into one email.
            </p>
          </div>

          <label className="digest-switch">
            <input
              type="checkbox"
              checked={preference.enabled}
              disabled={saving}
              onChange={(event) => {
                const enabled =
                  event.target.checked

                setPreference({
                  ...preference,
                  enabled,
                })
                setConfirmation(null)
              }}
            />

            <span
              className="digest-switch__track"
              aria-hidden="true"
            >
              <span />
            </span>

            <span className="digest-switch__copy">
              <strong>
                {preference.enabled
                  ? 'Weekly digest enabled'
                  : 'Weekly digest paused'}
              </strong>
              <small>
                {preference.enabled
                  ? (
                      'Send new intelligence '
                      + 'to my verified email.'
                    )
                  : (
                      'Keep intelligence '
                      + 'inside Outpace only.'
                    )}
              </small>
            </span>
          </label>

          <button
            className="digest-settings__save"
            type="submit"
            disabled={saving}
          >
            {saving
              ? 'Saving preference…'
              : 'Save preference'}
          </button>

          <div
            className="digest-settings__feedback"
            aria-live="polite"
          >
            {confirmation && (
              <p className="digest-settings__success">
                {confirmation}
              </p>
            )}

            {error && (
              <p
                className="digest-settings__error"
                role="alert"
              >
                {error}
              </p>
            )}
          </div>
        </form>
      </div>
    </main>
  )
}
