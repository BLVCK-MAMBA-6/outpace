import {
  useEffect,
  useMemo,
  useState,
} from 'react'
import type {
  ReactNode,
} from 'react'
import type {
  Session,
} from '@supabase/supabase-js'

import { supabase } from '../lib/supabase'
import {
  AuthContext,
} from './auth-context'

type AuthProviderProps = {
  children: ReactNode
}

export function AuthProvider({
  children,
}: AuthProviderProps) {
  const [session, setSession] =
    useState<Session | null>(null)
  const [loading, setLoading] =
    useState(true)

  useEffect(() => {
    let active = true

    void supabase.auth
      .getSession()
      .then(({ data, error }) => {
        if (!active) {
          return
        }

        if (error) {
          setSession(null)
        } else {
          setSession(data.session)
        }

        setLoading(false)
      })

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange(
      (_event, nextSession) => {
        if (!active) {
          return
        }

        setSession(nextSession)
        setLoading(false)
      },
    )

    return () => {
      active = false
      subscription.unsubscribe()
    }
  }, [])

  const value = useMemo(
    () => ({
      session,
      user: session?.user ?? null,
      loading,
      signOut: async () => {
        await supabase.auth.signOut()
      },
    }),
    [loading, session],
  )

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}
