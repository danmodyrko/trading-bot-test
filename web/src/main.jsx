import React, { useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
const API_TOKEN = import.meta.env.VITE_API_TOKEN || 'dev-token'

const routes = [
  { label: 'Dashboard', path: '/dashboard' },
  { label: 'Positions', path: '/positions' },
  { label: 'Orders', path: '/orders' },
  { label: 'Journal', path: '/journal' },
  { label: 'Settings', path: '/settings' }
]

const eventFilters = ['ALL', 'INFO', 'WARNING', 'ERROR', 'RISK', 'ORDER', 'FILL', 'SYSTEM']

const safeParse = (raw) => {
  try {
    return JSON.parse(raw || '{}')
  } catch {
    return null
  }
}

function App() {
  const [route, setRoute] = useState(window.location.pathname === '/' ? '/dashboard' : window.location.pathname)
  const [status, setStatus] = useState({ running: false, mode: 'DEMO', ws_connected: false, latency_ms: 0, uptime_seconds: 0 })
  const [account, setAccount] = useState({ balance: 0, equity: 0 })
  const [positions, setPositions] = useState([])
  const [orders, setOrders] = useState([])
  const [journal, setJournal] = useState([])
  const [settings, setSettings] = useState({})
  const [events, setEvents] = useState([])
  const [filter, setFilter] = useState('ALL')

  const headers = useMemo(() => ({ 'X-API-TOKEN': API_TOKEN, 'Content-Type': 'application/json' }), [])

  const api = async (path, options = {}) => {
    const response = await fetch(`${API_URL}${path}`, { ...options, headers: { ...headers, ...(options.headers || {}) } })
    if (!response.ok) throw new Error(`${path}: ${response.status}`)
    return response.json()
  }

  const loadAll = async () => {
    const [s, a, p, o, j, cfg] = await Promise.all([
      api('/api/status'),
      api('/api/account'),
      api('/api/positions'),
      api('/api/orders'),
      api('/api/journal?page=1&page_size=100'),
      api('/api/settings')
    ])
    setStatus(s)
    setAccount(a)
    setPositions(Array.isArray(p) ? p : [])
    setOrders(Array.isArray(o) ? o : [])
    setJournal(j.items || [])
    setSettings(cfg)
  }

  useEffect(() => {
    loadAll()
  }, [])

  useEffect(() => {
    const onPop = () => setRoute(window.location.pathname)
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  useEffect(() => {
    let ws
    let reconnect
    const connect = () => {
      ws = new WebSocket(`${API_URL.replace('http', 'ws')}/ws/events?token=${encodeURIComponent(API_TOKEN)}`)
      ws.onmessage = (msg) => {
        const data = JSON.parse(msg.data)
        if (data.type === 'snapshot') {
          setStatus(data.status || {})
          setSettings(data.settings || {})
          setPositions(data.positions || [])
          setOrders(data.orders || [])
          setEvents(data.events || [])
          return
        }
        if (data.type === 'status') {
          setStatus(data.status)
          return
        }
        if (data.type === 'event') {
          setEvents((prev) => [data.event, ...prev].slice(0, 1000))
        }
      }
      ws.onclose = () => {
        reconnect = setTimeout(connect, 1000)
      }
    }
    connect()
    return () => {
      if (reconnect) clearTimeout(reconnect)
      if (ws) ws.close()
    }
  }, [])

  const navigate = (path) => {
    window.history.pushState({}, '', path)
    setRoute(path)
  }

  const act = async (path) => {
    await api(path, { method: 'POST' })
    await loadAll()
  }

  const saveSettings = async () => {
    await api('/api/settings', { method: 'PUT', body: JSON.stringify(settings) })
    await loadAll()
  }

  const groupedSettings = {
    Connection: { mode: settings.mode, exchange: settings.exchange, endpoints: settings.endpoints, api: settings.api },
    Strategy: settings.strategy,
    Risk: settings.risk,
    Notifications: settings.ui
  }

  const filteredEvents = events.filter((evt) => {
    if (filter === 'ALL') return true
    return evt.category === filter || evt.level === filter
  })

  return <div className="h-screen flex bg-bg text-text">
    <aside className="w-64 border-r border-border bg-surface flex flex-col p-4">
      <h1 className="text-lg font-bold mb-4">Trader Bot Control Center</h1>
      <nav className="space-y-2">
        {routes.map((item) => <button key={item.path} onClick={() => navigate(item.path)} className={`w-full text-left px-3 py-2 rounded ${route===item.path?'bg-accent':'hover:bg-border'}`}>{item.label}</button>)}
      </nav>
    </aside>

    <main className="flex-1 p-3 overflow-auto space-y-3">
      <div className="card flex gap-3 items-center text-sm">
        <span className={`px-2 py-1 rounded ${status.running ? 'bg-success/20 text-success' : 'bg-danger/20 text-danger'}`}>{status.running ? 'RUNNING' : 'STOPPED'}</span>
        <span>WS: {String(status.ws_connected)}</span>
        <span>Latency: {status.latency_ms}ms</span>
        <span>Uptime: {status.uptime_seconds}s</span>
        <span className="ml-auto">Balance: {Number(account.balance || 0).toFixed(2)}</span>
        <span>Equity: {Number(account.equity || 0).toFixed(2)}</span>
        <button onClick={() => act('/api/start')} className="px-2 py-1 bg-success/20 rounded">Start</button>
        <button onClick={() => act('/api/stop')} className="px-2 py-1 bg-danger/20 rounded">Stop</button>
        <button onClick={() => act('/api/pause')} className="px-2 py-1 bg-border rounded">Pause</button>
        <button onClick={() => act('/api/resume')} className="px-2 py-1 bg-border rounded">Resume</button>
        <button onClick={() => act('/api/flatten')} className="px-2 py-1 bg-border rounded">Flatten</button>
        <button onClick={() => act('/api/kill')} className="px-2 py-1 bg-danger/30 rounded">Kill</button>
      </div>

      {route === '/dashboard' && <div className="grid grid-cols-2 gap-3">
        <div className="card">
          <h3 className="font-semibold mb-2">Terminal Feed (REAL events)</h3>
          <div className="flex gap-1 mb-2 flex-wrap">{eventFilters.map((f) => <button key={f} className={`text-xs px-2 py-1 rounded ${filter===f?'bg-accent':'bg-border'}`} onClick={() => setFilter(f)}>{f}</button>)}</div>
          <div className="text-xs space-y-1 max-h-80 overflow-y-auto">{filteredEvents.map((e, idx) => <div key={`${e.ts}-${idx}`} className="border-b border-border pb-1">{e.ts} [{e.category}/{e.level}] {e.message}</div>)}</div>
        </div>
        <div className="card text-sm">
          <h3 className="font-semibold mb-2">Overview</h3>
          <div>Mode: {status.mode}</div>
          <div>Open positions: {positions.length}</div>
          <div>Open orders: {orders.length}</div>
          <div>Journal rows: {journal.length}</div>
        </div>
      </div>}

      {route === '/positions' && <div className="card"><h3 className="font-semibold mb-2">Positions</h3><pre className="text-xs overflow-auto">{JSON.stringify(positions, null, 2)}</pre></div>}
      {route === '/orders' && <div className="card"><h3 className="font-semibold mb-2">Orders</h3><pre className="text-xs overflow-auto">{JSON.stringify(orders, null, 2)}</pre></div>}
      {route === '/journal' && <div className="card"><h3 className="font-semibold mb-2">Journal</h3><pre className="text-xs overflow-auto">{JSON.stringify(journal, null, 2)}</pre></div>}

      {route === '/settings' && <div className="space-y-3">
        {Object.entries(groupedSettings).map(([title, group]) => <div key={title} className="card">
          <h3 className="font-semibold mb-2">{title}</h3>
          <textarea className="w-full h-40 bg-bg border border-border rounded p-2 text-xs" value={JSON.stringify(group ?? {}, null, 2)} onChange={(e) => {
            const parsed = safeParse(e.target.value)
            if (!parsed) return
            if (title === 'Connection') {
              setSettings((prev) => ({ ...prev, mode: parsed.mode, exchange: parsed.exchange, endpoints: parsed.endpoints, api: parsed.api }))
            } else if (title === 'Strategy') {
              setSettings((prev) => ({ ...prev, strategy: parsed }))
            } else if (title === 'Risk') {
              setSettings((prev) => ({ ...prev, risk: parsed }))
            } else {
              setSettings((prev) => ({ ...prev, ui: parsed }))
            }
          }} />
        </div>)}
        <button onClick={saveSettings} className="px-3 py-2 bg-accent rounded">Save Settings</button>
      </div>}
    </main>
  </div>
}

createRoot(document.getElementById('root')).render(<App />)
