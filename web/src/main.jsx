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

const parseValue = (value) => {
  if (value === '') return ''
  const asNumber = Number(value)
  if (!Number.isNaN(asNumber) && /^-?\d+(\.\d+)?$/.test(value)) return asNumber
  return value
}

const prettyNumber = (value) => Number(value || 0).toFixed(2)

function SectionCard({ title, subtitle, children }) {
  return (
    <section className="card shadow-soft">
      <div className="mb-3">
        <h3 className="text-base font-semibold">{title}</h3>
        {subtitle && <p className="text-xs text-text-muted mt-1">{subtitle}</p>}
      </div>
      {children}
    </section>
  )
}

function StatusBadge({ active, activeText, idleText }) {
  return (
    <span className={`status-pill ${active ? 'status-pill-active' : 'status-pill-idle'}`}>
      {active ? activeText : idleText}
    </span>
  )
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
  const [saving, setSaving] = useState(false)

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
    setSaving(true)
    try {
      await api('/api/settings', { method: 'PUT', body: JSON.stringify(settings) })
      await loadAll()
    } finally {
      setSaving(false)
    }
  }

  const filteredEvents = events.filter((evt) => {
    if (filter === 'ALL') return true
    return evt.category === filter || evt.level === filter
  })

  const updateNested = (section, key, value) => {
    setSettings((prev) => ({
      ...prev,
      [section]: {
        ...(prev[section] || {}),
        [key]: value
      }
    }))
  }

  return <div className="min-h-screen flex bg-bg text-text">
    <aside className="w-64 border-r border-border bg-surface/90 backdrop-blur flex flex-col p-5 gap-6">
      <div>
        <p className="text-xs uppercase text-text-muted tracking-[0.2em]">Trading Bot</p>
        <h1 className="text-xl font-bold">Control Center</h1>
      </div>
      <nav className="space-y-2">
        {routes.map((item) => (
          <button
            key={item.path}
            onClick={() => navigate(item.path)}
            className={`nav-btn ${route === item.path ? 'nav-btn-active' : 'nav-btn-idle'}`}
          >
            {item.label}
          </button>
        ))}
      </nav>
      <div className="text-xs text-text-muted mt-auto space-y-1">
        <div>API: {API_URL}</div>
        <div>Mode: {status.mode || 'DEMO'}</div>
      </div>
    </aside>

    <main className="flex-1 p-5 overflow-auto space-y-4">
      <SectionCard title="Bot controls" subtitle="Quick actions with live health indicators.">
        <div className="flex flex-wrap gap-2 items-center text-sm">
          <StatusBadge active={status.running} activeText="Running" idleText="Stopped" />
          <StatusBadge active={status.ws_connected} activeText="Realtime connected" idleText="Realtime offline" />
          <span className="metric-chip">Latency: {status.latency_ms}ms</span>
          <span className="metric-chip">Uptime: {status.uptime_seconds}s</span>
          <span className="metric-chip">Balance: {prettyNumber(account.balance)}</span>
          <span className="metric-chip">Equity: {prettyNumber(account.equity)}</span>
        </div>
        <div className="flex flex-wrap gap-2 mt-3">
          <button onClick={() => act('/api/start')} className="action-btn action-good">Start</button>
          <button onClick={() => act('/api/stop')} className="action-btn action-bad">Stop</button>
          <button onClick={() => act('/api/pause')} className="action-btn">Pause</button>
          <button onClick={() => act('/api/resume')} className="action-btn">Resume</button>
          <button onClick={() => act('/api/flatten')} className="action-btn">Flatten</button>
          <button onClick={() => act('/api/kill')} className="action-btn action-bad">Emergency Kill</button>
        </div>
      </SectionCard>

      {route === '/dashboard' && <div className="grid xl:grid-cols-3 gap-4">
        <SectionCard title="Live events" subtitle="Use filters to focus on warnings, risk, or order activity.">
          <div className="flex gap-1 mb-3 flex-wrap">
            {eventFilters.map((f) => (
              <button key={f} className={`chip ${filter === f ? 'chip-active' : ''}`} onClick={() => setFilter(f)}>{f}</button>
            ))}
          </div>
          <div className="text-xs space-y-2 max-h-[420px] overflow-y-auto pr-1">
            {filteredEvents.map((e, idx) => (
              <div key={`${e.ts}-${idx}`} className="event-row">
                <p className="text-text-muted">{e.ts}</p>
                <p>[{e.category}/{e.level}] {e.message}</p>
              </div>
            ))}
            {filteredEvents.length === 0 && <p className="text-text-muted">No events in this category yet.</p>}
          </div>
        </SectionCard>

        <SectionCard title="Portfolio summary" subtitle="Current account and activity snapshot.">
          <dl className="stats-grid">
            <div><dt>Mode</dt><dd>{status.mode}</dd></div>
            <div><dt>Open positions</dt><dd>{positions.length}</dd></div>
            <div><dt>Open orders</dt><dd>{orders.length}</dd></div>
            <div><dt>Journal rows</dt><dd>{journal.length}</dd></div>
          </dl>
        </SectionCard>

        <SectionCard title="Next step" subtitle="If API is not configured, start in demo mode and connect credentials in Settings.">
          <p className="text-sm text-text-muted leading-relaxed">
            This interface is optimized for quick decision-making: review health at the top,
            inspect events in one place, and update bot settings with form fields instead of raw JSON.
          </p>
        </SectionCard>
      </div>}

      {route === '/positions' && <SectionCard title="Positions" subtitle="Readable table of active positions.">
        <div className="table-wrap">
          <table className="data-table">
            <thead><tr><th>Symbol</th><th>Side</th><th>Qty</th><th>Entry</th><th>Mark</th><th>PnL</th></tr></thead>
            <tbody>
              {positions.map((row, idx) => <tr key={`${row.symbol || 'row'}-${idx}`}>
                <td>{row.symbol || '-'}</td><td>{row.side || '-'}</td><td>{row.qty ?? '-'}</td>
                <td>{row.entry_price ?? '-'}</td><td>{row.mark_price ?? '-'}</td><td>{row.pnl ?? '-'}</td>
              </tr>)}
              {positions.length === 0 && <tr><td colSpan="6" className="text-center text-text-muted">No open positions</td></tr>}
            </tbody>
          </table>
        </div>
      </SectionCard>}

      {route === '/orders' && <SectionCard title="Orders" subtitle="Latest order activity.">
        <div className="table-wrap">
          <table className="data-table">
            <thead><tr><th>Symbol</th><th>Type</th><th>Side</th><th>Qty</th><th>Price</th><th>Status</th></tr></thead>
            <tbody>
              {orders.map((row, idx) => <tr key={`${row.id || 'order'}-${idx}`}>
                <td>{row.symbol || '-'}</td><td>{row.type || '-'}</td><td>{row.side || '-'}</td>
                <td>{row.qty ?? '-'}</td><td>{row.price ?? '-'}</td><td>{row.status || '-'}</td>
              </tr>)}
              {orders.length === 0 && <tr><td colSpan="6" className="text-center text-text-muted">No open orders</td></tr>}
            </tbody>
          </table>
        </div>
      </SectionCard>}

      {route === '/journal' && <SectionCard title="Journal" subtitle="Recent actions and decision logs.">
        <div className="table-wrap">
          <table className="data-table">
            <thead><tr><th>Time</th><th>Action</th><th>Details</th></tr></thead>
            <tbody>
              {journal.map((row, idx) => <tr key={`${row.ts || 'journal'}-${idx}`}>
                <td>{row.ts || '-'}</td><td>{row.action || row.type || '-'}</td><td>{row.message || JSON.stringify(row)}</td>
              </tr>)}
              {journal.length === 0 && <tr><td colSpan="3" className="text-center text-text-muted">Journal is empty</td></tr>}
            </tbody>
          </table>
        </div>
      </SectionCard>}

      {route === '/settings' && <div className="grid lg:grid-cols-2 gap-4">
        <SectionCard title="Connection" subtitle="Friendly connection controls (no raw JSON required).">
          <div className="form-grid">
            <label>Mode
              <select value={settings.mode || 'DEMO'} onChange={(e) => setSettings((prev) => ({ ...prev, mode: e.target.value }))}>
                <option value="DEMO">DEMO</option>
                <option value="LIVE">LIVE</option>
              </select>
            </label>
            <label>Exchange
              <input value={settings.exchange || ''} placeholder="e.g. binance" onChange={(e) => setSettings((prev) => ({ ...prev, exchange: e.target.value }))} />
            </label>
            <label>REST endpoint
              <input value={settings.endpoints?.rest || ''} placeholder="https://api.exchange.com" onChange={(e) => updateNested('endpoints', 'rest', e.target.value)} />
            </label>
            <label>WebSocket endpoint
              <input value={settings.endpoints?.ws || ''} placeholder="wss://stream.exchange.com/ws" onChange={(e) => updateNested('endpoints', 'ws', e.target.value)} />
            </label>
            <label>API key
              <input value={settings.api?.key || ''} placeholder="Optional" onChange={(e) => updateNested('api', 'key', e.target.value)} />
            </label>
            <label>API secret
              <input type="password" value={settings.api?.secret || ''} placeholder="Optional" onChange={(e) => updateNested('api', 'secret', e.target.value)} />
            </label>
          </div>
        </SectionCard>

        <SectionCard title="Strategy & Risk" subtitle="Common controls surfaced as simple fields.">
          <div className="form-grid">
            <label>Symbol
              <input value={settings.strategy?.symbol || ''} placeholder="BTCUSDT" onChange={(e) => updateNested('strategy', 'symbol', e.target.value)} />
            </label>
            <label>Timeframe
              <input value={settings.strategy?.timeframe || ''} placeholder="1m / 5m / 1h" onChange={(e) => updateNested('strategy', 'timeframe', e.target.value)} />
            </label>
            <label>Order size
              <input value={settings.strategy?.order_size ?? ''} placeholder="0.01" onChange={(e) => updateNested('strategy', 'order_size', parseValue(e.target.value))} />
            </label>
            <label>Max positions
              <input value={settings.risk?.max_positions ?? ''} placeholder="3" onChange={(e) => updateNested('risk', 'max_positions', parseValue(e.target.value))} />
            </label>
            <label>Daily loss limit
              <input value={settings.risk?.daily_loss_limit ?? ''} placeholder="100" onChange={(e) => updateNested('risk', 'daily_loss_limit', parseValue(e.target.value))} />
            </label>
            <label>Stop loss %
              <input value={settings.risk?.stop_loss_pct ?? ''} placeholder="2" onChange={(e) => updateNested('risk', 'stop_loss_pct', parseValue(e.target.value))} />
            </label>
          </div>
          <button onClick={saveSettings} className="action-btn action-good mt-4" disabled={saving}>{saving ? 'Saving...' : 'Save Settings'}</button>
        </SectionCard>
      </div>}
    </main>
  </div>
}

createRoot(document.getElementById('root')).render(<App />)
