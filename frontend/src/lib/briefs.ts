import type {
  Brief,
} from './types'

export function isControlledBrief(
  brief: Brief,
) {
  const synthesis = brief.synthesis ?? {}
  const searchable = [
    synthesis.headline,
    synthesis.summary,
    synthesis.why_it_matters,
    synthesis.recommended_action,
    ...(synthesis.evidence ?? []),
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()

  return (
    searchable.includes('[test data]') ||
    searchable.includes('controlled pipeline test') ||
    searchable.includes('synthetic test') ||
    searchable.includes('test fixture')
  )
}
