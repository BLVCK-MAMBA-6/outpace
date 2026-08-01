import '@fontsource/instrument-serif/400.css'
import '@fontsource/space-grotesk/400.css'
import '@fontsource/space-grotesk/500.css'
import '@fontsource/space-grotesk/600.css'
import '@fontsource/jetbrains-mono/400.css'
import '@fontsource/jetbrains-mono/600.css'

import { createRoot } from 'react-dom/client'

import { App } from './app/App'
import './styles/global.css'
import './styles/refinement.css'
import './styles/digest-settings.css'

const root = document.getElementById('root')

if (!root) {
  throw new Error('Root element not found')
}

createRoot(root).render(<App />)
