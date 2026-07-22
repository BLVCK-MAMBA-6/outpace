import type {
  ReactNode,
} from 'react'
import {
  Navigate,
  useLocation,
} from 'react-router-dom'

import { useAuth } from '../hooks/useAuth'

type GuardProps = {
  children: ReactNode
}

function SessionLoading() {
  return (
    <main className="session-loading">
      <p className="eyebrow">
        SESSION RESTORE
      </p>
      <h1>
        Loading your intelligence stream.
      </h1>
      <div className="status-track">
        <span />
      </div>
    </main>
  )
}

export function ProtectedRoute({
  children,
}: GuardProps) {
  const {
    session,
    loading,
  } = useAuth()
  const location = useLocation()

  if (loading) {
    return <SessionLoading />
  }

  if (!session) {
    return (
      <Navigate
        replace
        to="/login"
        state={{
          from: location.pathname,
        }}
      />
    )
  }

  return children
}

export function PublicOnlyRoute({
  children,
}: GuardProps) {
  const {
    session,
    loading,
  } = useAuth()

  if (loading) {
    return <SessionLoading />
  }

  if (session) {
    return (
      <Navigate
        replace
        to="/dashboard"
      />
    )
  }

  return children
}
