export type AuthenticatedUser = {
  id: string
  email: string | null
}

export type Competitor = {
  id: string
  user_id: string
  name: string
  website_url: string
  pricing_url: string | null
  created_at: string
  updated_at: string
}

export type BriefSynthesis = {
  headline?: string
  summary?: string
  why_it_matters?: string
  recommended_action?: string
  evidence?: string[]
  confidence?: number
  priority?: string
}

export type Brief = {
  id: string
  competitor_id: string
  signal_type: string
  synthesis: BriefSynthesis
  priority: string
  delivered: boolean
  created_at: string
}

export type CompetitorCreate = {
  name: string
  website_url: string
  pricing_url?: string | null
}

export type SignalType =
  | 'general'
  | 'pricing'
  | 'reviews'
  | 'jobs'
  | 'news'

export type MonitoringSignalStatus = {
  signal_type: SignalType
  configured: boolean
  enabled: boolean
  source_id: string | null
  provider: string | null
  source_url: string | null
  last_polled_at: string | null
  latest_snapshot_id: string | null
  latest_snapshot_at: string | null
}

export type CompetitorMonitoring = {
  competitor: Competitor
  signals: MonitoringSignalStatus[]
}

export type TaskQueued = {
  status: 'queued'
  task_id: string
  signal_type: SignalType
  target_id: string
}

export type TaskStatus = {
  task_id: string
  state: string
  ready: boolean
  successful: boolean | null
  result: Record<string, unknown> | null
  error: string | null
}
