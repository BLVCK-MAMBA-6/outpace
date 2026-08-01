import {
  NavLink,
  Outlet,
  useNavigate,
} from 'react-router'

import { BrandMark } from '../components/BrandMark'
import { useAuth } from '../hooks/useAuth'

export function AppLayout() {
  const {
    user,
    signOut,
  } = useAuth()
  const navigate = useNavigate()

  async function handleSignOut() {
    await signOut()
    navigate('/login', {
      replace: true,
    })
  }

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <div className="app-sidebar__brand">
          <BrandMark compact />
        </div>

        <nav
          className="app-nav"
          aria-label="Workspace"
        >
          <p className="app-nav__label">
            WORKSPACE
          </p>

          <NavLink to="/dashboard">
            <span>01</span>
            Overview
          </NavLink>

          <NavLink to="/onboarding">
            <span>02</span>
            Add competitor
          </NavLink>

          <NavLink to="/settings/digest">
            <span>03</span>
            Digest settings
          </NavLink>
        </nav>

        <div className="app-sidebar__account">
          <span className="connection-line">
            <i aria-hidden="true" />
            API CONNECTED
          </span>
          <p title={user?.email ?? ''}>
            {user?.email ?? 'Authenticated user'}
          </p>
          <button
            type="button"
            onClick={() => {
              void handleSignOut()
            }}
          >
            Sign out →
          </button>
        </div>
      </aside>

      <div className="app-workspace">
        <header className="app-topbar">
          <span>
            OUTPACE / MONITOR
          </span>
          <span>
            USER-SCOPED INTELLIGENCE
          </span>
        </header>

        <Outlet />
      </div>
    </div>
  )
}
