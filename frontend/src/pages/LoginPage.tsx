import {
  useState,
} from 'react'
import type {
  FormEvent,
} from 'react'
import { Link } from 'react-router'

import { BrandMark } from '../components/BrandMark'
import { supabase } from '../lib/supabase'

export function LoginPage() {
  const [email, setEmail] =
    useState('')
  const [submitting, setSubmitting] =
    useState(false)
  const [sent, setSent] =
    useState(false)
  const [error, setError] =
    useState<string | null>(null)

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault()
    setError(null)

    const normalizedEmail =
      email.trim().toLowerCase()

    if (
      !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(
        normalizedEmail,
      )
    ) {
      setError(
        'Enter a valid work email address.',
      )
      return
    }

    setSubmitting(true)

    try {
      const { error: authError } =
        await supabase.auth.signInWithOtp({
          email: normalizedEmail,
          options: {
            emailRedirectTo:
              `${window.location.origin}/auth/callback`,
            shouldCreateUser: true,
          },
        })

      if (authError) {
        setError(
          'We could not send the sign-in link. Please try again.',
        )
        return
      }

      setSent(true)
    } catch {
      setError(
        'The sign-in service is temporarily unavailable. Try again shortly.',
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="lux-auth">
      <section className="lux-auth__story">
        <header>
          <BrandMark />
          <Link to="/">
            Back to home
          </Link>
        </header>

        <div className="lux-auth__message">
          <p className="lux-kicker">
            Welcome to Outpace
          </p>
          <h1>
            Your competitive edge,
            <span>
              always within view.
            </span>
          </h1>
          <p>
            Return to a clear view of competitor
            movement, evidence, and the decisions
            waiting for your attention.
          </p>
        </div>

        <div className="login-insight-preview">
          <div className="login-insight-preview__header">
            <span>Today’s market pulse</span>
            <span>Monitoring active</span>
          </div>

          <svg
            viewBox="0 0 500 130"
            aria-hidden="true"
          >
            <path
              d="M0 105 C55 95 70 108 118 83 C160 61 188 91 231 67 C278 40 306 72 350 48 C395 22 420 44 500 14"
            />
          </svg>

          <div className="login-insight-preview__footer">
            <span>
              Websites
            </span>
            <span>
              Pricing
            </span>
            <span>
              Reviews
            </span>
            <span>
              Hiring
            </span>
            <span>
              News
            </span>
          </div>
        </div>
      </section>

      <section className="lux-auth__entry">
        <div className="lux-auth__form-wrap">
          {!sent ? (
            <>
              <p className="lux-kicker">
                Secure sign in
              </p>
              <h2>
                Continue to your workspace.
              </h2>
              <p className="lux-auth__intro">
                Enter your email and we’ll send
                you a secure one-time sign-in
                link. No password required.
              </p>

              <form
                className="lux-auth-form"
                onSubmit={(event) => {
                  void handleSubmit(event)
                }}
              >
                <label htmlFor="email">
                  Work email
                </label>

                <input
                  id="email"
                  autoComplete="email"
                  inputMode="email"
                  name="email"
                  placeholder="you@company.com"
                  required
                  type="email"
                  aria-describedby={
                    error
                      ? 'email-error'
                      : 'email-help'
                  }
                  aria-invalid={Boolean(error)}
                  value={email}
                  onChange={(event) => {
                    setEmail(
                      event.target.value,
                    )
                    if (error) {
                      setError(null)
                    }
                  }}
                />

                {error && (
                  <p
                    className="form-error"
                    id="email-error"
                    role="alert"
                  >
                    {error}
                  </p>
                )}

                <button
                  className="lux-button lux-button--primary"
                  disabled={submitting}
                  type="submit"
                >
                  {submitting
                    ? 'Sending your link…'
                    : 'Email me a sign-in link'}
                </button>
              </form>

              <p className="lux-auth__privacy">
                <span id="email-help">
                  One secure link. No password
                  to create or remember.
                </span>
              </p>
            </>
          ) : (
            <div
              className="lux-auth-success"
              aria-live="polite"
            >
              <div className="success-mark">
                ✓
              </div>
              <p className="lux-kicker">
                Link sent
              </p>
              <h2>
                Check your inbox.
              </h2>
              <p>
                We sent a secure sign-in link to{' '}
                <strong>{email.trim()}</strong>.
                Open it in this browser to
                continue.
              </p>
              <button
                className="lux-text-button"
                type="button"
                onClick={() => {
                  setSent(false)
                }}
              >
                Use another email
              </button>
            </div>
          )}
        </div>

        <footer>
          <span>
            Private by design
          </span>
          <span>
            Your data remains isolated
          </span>
        </footer>
      </section>
    </main>
  )
}
