import { lazy, Suspense } from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import { ProtectedRoute } from './components/ProtectedRoute'
import { Layout } from './components/Layout'
import { Login } from './pages/Login'
import './App.css'

const Overview = lazy(() => import('./pages/Overview').then(m => ({ default: m.Overview })))
const LiveFeed = lazy(() => import('./pages/LiveFeed').then(m => ({ default: m.LiveFeed })))
const Venues = lazy(() => import('./pages/Venues').then(m => ({ default: m.Venues })))
const Orders = lazy(() => import('./pages/Orders').then(m => ({ default: m.Orders })))
const Risk = lazy(() => import('./pages/Risk').then(m => ({ default: m.Risk })))
const Alerts = lazy(() => import('./pages/Alerts').then(m => ({ default: m.Alerts })))

function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<Navigate to="/overview" replace />} />
          <Route path="/*" element={
            <ProtectedRoute>
              <Layout>
                <Suspense fallback={<div className="flex items-center justify-center p-8">Loading...</div>}>
                  <Routes>
                    <Route path="/overview" element={<Overview />} />
                    <Route path="/live" element={<LiveFeed />} />
                    <Route path="/venues" element={<Venues />} />
                    <Route path="/orders" element={<Orders />} />
                    <Route path="/alerts" element={<Alerts />} />
                    <Route path="/risk" element={
                      <ProtectedRoute requireRole="controller">
                        <Risk />
                      </ProtectedRoute>
                    } />
                  </Routes>
                </Suspense>
              </Layout>
            </ProtectedRoute>
          } />
        </Routes>
      </Router>
    </AuthProvider>
  )
}

export default App
