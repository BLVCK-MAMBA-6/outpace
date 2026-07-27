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

export type SourceHealthStatus =
  | 'unconfigured'
  | 'disabled'
  | 'pending'
  | 'healthy'
  | 'degraded'
  | 'blocked'
  | 'unsupported'
  | 'failed'

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
  health_status: SourceHealthStatus
  last_attempt_at: string | null
  last_success_at: string | null
  last_failure_at: string | null
  last_error_code: string | null
  last_error_message: string | null
  consecutive_failures: number
}

export type CompetitorMonitoring = {
  competitor: Competitor
  signals: MonitoringSignalStatus[]
}

export type MonitoringSource = {
  id: string
  competitor_id: string
  signal_type: 'jobs' | 'news'
  provider: string
  source_url: string
  enabled: boolean
}

export type JobSourceCreate = {
  provider:
    | 'html'
    | 'github'
    | 'ashby'
    | 'greenhouse'
    | 'lever'
    | 'deel'
  source_url: string
  external_source_id?: string
  region?: 'global' | 'eu'
  board_name?: string
  job_link_path?: string
  branch?: string
  readme_path?: string
}

export type JobSourceDiscovery = {
  provider: JobSourceCreate['provider']
  source_url: string
  external_source_id: string | null
  region: 'global' | 'eu' | null
  confidence: 'high' | 'medium' | 'low'
  detected_by:
    | 'direct_url'
    | 'embedded_reference'
    | 'verified_company_slug'
    | 'public_html_fallback'
  job_count: number | null
  requires_confirmation: boolean
  message: string
  metadata: Record<string, unknown>
}

export type NewsSourceCreate = {
  provider: 'html'
  source_url: string
  article_link_path?: string
  keywords?: string[]
  max_articles?: number
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
