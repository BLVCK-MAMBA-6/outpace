import {
  useEffect,
  useState,
} from 'react'
import {
  Link,
  useNavigate,
} from 'react-router-dom'

import { BrandMark } from '../components/BrandMark'
import { apiRequest } from '../lib/api'
import { supabase } from '../lib/supabase'
import type {
  Competitor,
} from '../lib/types'

type CallbackState =
  | 'verifying'
  | 'session'
  | 'workspace'
  | 'failed'

export function AuthCallbackPage() {
  const navigate = useNavigate()
  const [state, setState] =
    useState<CallbackState>('verifying')
  const [message, setMessage] =
    useState(
      'Checking the one-time authorization code.',
    )

  useEffect(() => {
    let active = true

    async function completeLogin() {
      try {
        const params =
          new URLSearchParams(
            window.location.search,
          )
        const code = params.get('code')

        const {
          data: existing,
        } = await supabase.auth.getSession()

        if (!existing.session) {
          if (!code) {
            throw new Error(
              'Missing authentication code',
            )
          }

          const { error } =
            await supabase.auth
              .exchangeCodeForSession(code)

          if (error) {
            throw error
          }
        }

        if (!active) {
          return
        }

        window.history.replaceState(
          {},
          document.title,
          '/auth/callback',
        )

        setState('session')
        setMessage(
          'Session created. Validating API access.',
        )

        await apiRequest('/auth/me')

        if (!active) {
          return
        }

        setState('workspace')
        setMessage(
          'Authentication complete. Loading workspace.',
        )

        const competitors =
          await apiRequest<Competitor[]>(
            '/competitors/',
          )

        if (!active) {
          return
        }

        navigate(
          competitors.length > 0
            ? '/dashboard'
            : '/onboarding',
          {
            replace: true,
          },
        )
      } catch {
        if (!active) {
          return
        }

        setState('failed')
        setMessage(
          'This sign-in link is invalid, expired, or was opened in a different browser.',
        )
      }
    }

    void completeLogin()

    return () => {
      active = false
    }
  }, [navigate])

  return (
    <main className="callback-page">
      <header>
        <BrandMark />
        <span className="eyebrow">
          AUTHENTICATION SEQUENCE
        </span>
      </header>

      <section>
        <p className="eyebrow">
          SECURE SESSION
        </p>
        <h1>
          {state === 'failed'
            ? 'Access could not be verified.'
            : 'Opening your intelligence workspace.'}
        </h1>

        <ol className="callback-steps">
          <li
            className={
              state !== 'verifying'
                ? 'complete'
                : 'active'
            }
          >
            <span>01</span>
            LINK VERIFIED
          </li>
          <li
            className={
              state === 'session' ||
              state === 'workspace'
                ? 'active'
                : state === 'failed'
                  ? ''
                  : ''
            }
          >
            <span>02</span>
            SESSION CREATED
          </li>
          <li
            className={
              state === 'workspace'
                ? 'active'
                : ''
            }
          >
            <span>03</span>
            WORKSPACE LOADING
          </li>
        </ol>

        <p
          className={
            state === 'failed'
              ? 'callback-message callback-message--error'
              : 'callback-message'
          }
          aria-live="polite"
        >
          {message}
        </p>

        {state === 'failed' && (
          <Link
            className="button button--primary"
            to="/login"
          >
            Request a new link
          </Link>
        )}
      </section>
    </main>
  )
}
