import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Overview } from './pages/Overview'
import { LiveFeed } from './pages/LiveFeed'
import { Venues } from './pages/Venues'
import { Orders } from './pages/Orders'
import { Risk } from './pages/Risk'
import { Alerts } from './pages/Alerts'
import './App.css'

function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<Navigate to="/overview" replace />} />
          <Route path="/overview" element={<Overview />} />
          <Route path="/live" element={<LiveFeed />} />
          <Route path="/venues" element={<Venues />} />
          <Route path="/orders" element={<Orders />} />
          <Route path="/risk" element={<Risk />} />
          <Route path="/alerts" element={<Alerts />} />
        </Routes>
      </Layout>
    </Router>
  )
}

export default App
