import { useState, useEffect } from 'react'
import { BrowserRouter as Router, Routes, Route, Link, Navigate } from 'react-router-dom'
import { Layout, Home, Users, FileText, LogOut, Plus, Upload, Search, Calendar, ShieldCheck } from 'lucide-react'
import Dashboard from './components/Dashboard'
import PatientDetail from './components/PatientDetail'
import Login from './components/Login'

const MainLayout = ({ children, user }) => {
  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <nav className="sticky top-0 z-50 bg-white/80 backdrop-blur-md border-b border-slate-200 px-6 py-3 flex justify-between items-center">
        <Link to="/" className="text-2xl font-extrabold tracking-tight flex items-center gap-2">
          <span className="text-primary">E</span>mil<span className="text-primary">Y</span>
        </Link>
        <div className="flex items-center gap-6">
          <Link to="/" className="text-slate-600 hover:text-primary font-semibold flex items-center gap-2 transition-colors">
            <Home size={18} /> Home
          </Link>
          <Link to="/patients" className="text-slate-600 hover:text-primary font-semibold flex items-center gap-2 transition-colors">
            <Users size={18} /> Patients
          </Link>
          <Link to="/results" className="text-slate-600 hover:text-primary font-semibold flex items-center gap-2 transition-colors">
            <FileText size={18} /> Results
          </Link>
          <button className="text-slate-600 hover:text-danger font-semibold flex items-center gap-2 transition-colors">
            <LogOut size={18} /> Logout
          </button>
        </div>
      </nav>

      <main className="flex-1 container mx-auto p-8 max-w-7xl">
        {children}
      </main>

      <footer className="py-8 text-center text-slate-500 border-t border-slate-200 bg-white">
        <p>&copy; 2025 EmilY. Precision document analysis.</p>
      </footer>
    </div>
  )
}

function App() {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Simulate checking auth
    const checkAuth = async () => {
      try {
        // In real app, call API
        // const res = await axios.get('/api/auth/me')
        // setUser(res.data)
      } catch (err) {
        console.error(err)
      } finally {
        setLoading(false)
      }
    }
    checkAuth()
  }, [])

  if (loading) return <div className="h-screen flex items-center justify-center">Loading...</div>

  return (
    <Router>
      <Routes>
        <Route path="/login" element={<Login onLogin={setUser} />} />
        <Route 
          path="/*" 
          element={
            <MainLayout user={user}>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/patient/:id" element={<PatientDetail />} />
                {/* Fallback */}
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </MainLayout>
          } 
        />
      </Routes>
    </Router>
  )
}

export default App
