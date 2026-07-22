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
