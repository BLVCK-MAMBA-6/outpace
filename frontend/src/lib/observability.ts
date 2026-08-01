import * as Sentry from '@sentry/react'

const sensitiveHeaders = new Set([
  'authorization',
  'cookie',
  'set-cookie',
  'x-api-key',
  'apikey',
])

const sensitiveDataKeys = new Set([
  'access_token',
  'body',
  'code',
  'cookies',
  'data',
  'email',
  'password',
  'query',
  'query_string',
  'refresh_token',
  'token',
])

function stripUrl(value: string) {
  return value.split(/[?#]/, 1)[0]
}

function scrubHeaders(
  headers: Record<string, string> | undefined,
) {
  if (!headers) {
    return headers
  }

  return Object.fromEntries(
    Object.entries(headers).map(
      ([name, value]) => [
        name,
        sensitiveHeaders.has(
          name.toLowerCase(),
        )
          ? '[Filtered]'
          : value,
      ],
    ),
  )
}

export function initializeObservability() {
  const dsn = (
    import.meta.env.VITE_SENTRY_DSN as
      | string
      | undefined
  )?.trim()

  if (!dsn) {
    return false
  }

  const environment = (
    import.meta.env.VITE_SENTRY_ENVIRONMENT as
      | string
      | undefined
  )?.trim() || 'development'

  const release = (
    import.meta.env.VITE_SENTRY_RELEASE as
      | string
      | undefined
  )?.trim()

  Sentry.init({
    dsn,
    environment,
    release: release || undefined,
    sendDefaultPii: false,
    tracesSampleRate: 0,
    maxBreadcrumbs: 50,
    beforeSend(event) {
      delete event.user

      if (event.request) {
        if (event.request.url) {
          event.request.url = stripUrl(
            event.request.url,
          )
        }

        event.request.headers = scrubHeaders(
          event.request.headers,
        )

        delete event.request.cookies
        delete event.request.data
        delete event.request.env
        delete event.request.query_string
      }

      if (event.breadcrumbs) {
        event.breadcrumbs =
          event.breadcrumbs.map(
            (breadcrumb) => {
              if (!breadcrumb.data) {
                return breadcrumb
              }

              const data = {
                ...breadcrumb.data,
              }

              for (const key of Object.keys(data)) {
                const normalized =
                  key.toLowerCase()

                if (
                  normalized === 'url' &&
                  typeof data[key] === 'string'
                ) {
                  data[key] = stripUrl(
                    data[key],
                  )
                } else if (
                  normalized === 'headers' &&
                  typeof data[key] === 'object'
                ) {
                  data[key] = scrubHeaders(
                    data[key] as Record<
                      string,
                      string
                    >,
                  )
                } else if (
                  sensitiveDataKeys.has(
                    normalized,
                  ) ||
                  sensitiveHeaders.has(
                    normalized,
                  )
                ) {
                  data[key] = '[Filtered]'
                }
              }

              return {
                ...breadcrumb,
                data,
              }
            },
          )
      }

      return event
    },
  })

  Sentry.setTag(
    'service',
    'web',
  )

  return true
}
