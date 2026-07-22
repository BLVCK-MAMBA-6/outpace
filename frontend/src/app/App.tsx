import {
  BrowserRouter,
  Route,
  Routes,
} from 'react-router-dom'

import {
  ProtectedRoute,
  PublicOnlyRoute,
} from '../components/RouteGuards'
import {
  AuthProvider,
} from '../contexts/AuthProvider'
import { AppLayout } from '../layouts/AppLayout'
import {
  AuthCallbackPage,
} from '../pages/AuthCallbackPage'
import {
  DashboardPage,
} from '../pages/DashboardPage'
import {
  LandingPage,
} from '../pages/LandingPage'
import {
  LoginPage,
} from '../pages/LoginPage'
import {
  NotFoundPage,
} from '../pages/NotFoundPage'
import {
  OnboardingPage,
} from '../pages/OnboardingPage'

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route
            path="/"
            element={<LandingPage />}
          />

          <Route
            path="/login"
            element={
              <PublicOnlyRoute>
                <LoginPage />
              </PublicOnlyRoute>
            }
          />

          <Route
            path="/auth/callback"
            element={
              <AuthCallbackPage />
            }
          />

          <Route
            element={
              <ProtectedRoute>
                <AppLayout />
              </ProtectedRoute>
            }
          >
            <Route
              path="/dashboard"
              element={<DashboardPage />}
            />
            <Route
              path="/onboarding"
              element={<OnboardingPage />}
            />
          </Route>

          <Route
            path="*"
            element={<NotFoundPage />}
          />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
