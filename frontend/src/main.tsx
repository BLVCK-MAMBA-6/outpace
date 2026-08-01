import '@fontsource/instrument-serif/400.css'
import '@fontsource/space-grotesk/400.css'
import '@fontsource/space-grotesk/500.css'
import '@fontsource/space-grotesk/600.css'
import '@fontsource/jetbrains-mono/400.css'
import '@fontsource/jetbrains-mono/600.css'

import * as Sentry from '@sentry/react'
import { createRoot } from 'react-dom/client'

import { App } from './app/App'
import {
  initializeObservability,
} from './lib/observability'
import './styles/global.css'
import './styles/refinement.css'
import './styles/digest-settings.css'

initializeObservability()

const root = document.getElementById('root')

if (!root) {
  throw new Error('Root element not found')
}

createRoot(root).render(
  <Sentry.ErrorBoundary
    fallback={
      <main className="workspace-state">
        <p className="eyebrow">
          APPLICATION ERROR
        </p>
        <h1>
          Outpace hit an unexpected problem.
        </h1>
        <p>
          Refresh the page and try again.
        </p>
        <button
          type="button"
          onClick={() => {
            window.location.reload()
          }}
        >
          Reload Outpace
        </button>
      </main>
    }
  >
    <App />
  </Sentry.ErrorBoundary>,
)
