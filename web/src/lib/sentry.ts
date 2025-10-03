import * as Sentry from '@sentry/react'

export function initSentry() {
  const dsn = import.meta.env.VITE_SENTRY_DSN
  
  if (!dsn) {
    console.warn('Sentry DSN not configured')
    return
  }

  Sentry.init({
    dsn,
    environment: import.meta.env.VITE_ENV || 'development',
    release: import.meta.env.VITE_BUILD_SHA,
    integrations: [
      new Sentry.BrowserTracing(),
      new Sentry.Replay()
    ],
    tracesSampleRate: 0.1,
    replaysSessionSampleRate: 0.1,
    replaysOnErrorSampleRate: 1.0,
    beforeSend(event) {
      if (event.request?.cookies) {
        delete event.request.cookies
      }
      return event
    }
  })
}
