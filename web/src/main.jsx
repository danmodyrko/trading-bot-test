import React, { useEffect, useMemo, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
const API_TOKEN = import.meta.env.VITE_API_TOKEN || 'dev-token'

const navItems = ['Dashboard', 'Positions', 'Orders', 'Journal', 'Settings']
const logFilters = ['ALL', 'WS', 'SIGNAL', 'ORDER', 'FILL', 'RISK', 'ERROR']

function App() {
  const [page, setPage] = useState('Dashboard')
  const [status, setStatus] = useState({ running: false, mode: 'DEMO', ws_latency_ms: 0, balance: 0, equity: 0, daily_pnl: 0 })
  const [settings, setSettings] = useState({ active_profile: 'SAFE' })
  const [positions, setPositions] = useState([])
  const [orders, setOrders] = useState([])
  const [signals, setSignals] = useState([])
  const [events, setEvents] = useState([])
  const [filter, setFilter] = useState('ALL')
  const [conn, setConn] = useState({ state: 'disconnected', latency: 0, retry: 0 })
  const lastPingRef = useRef(0)

  const headers = useMemo(() => ({ 'X-API-TOKEN': API_TOKEN, 'Content-Type': 'application/json' }), [])

  const api = async (path, options = {}) => {
    const res = await fetch(`${API_URL}${path}`, { ...options, headers: { ...headers, ...(options.headers || {}) } })
    return res.json()
  }

  const refreshInitial = async () => {
    const [s, cfg, p, o, sig] = await Promise.all([
      api('/api/status'),
      api('/api/settings'),
      api('/api/positions'),
      api('/api/orders'),
      api('/api/signals')
    ])
    setStatus(s); setSettings(cfg); setPositions(p); setOrders(o); setSignals(sig)
  }

  useEffect(() => { refreshInitial() }, [])

  useEffect(() => {
    let ws
    let retryTimer
    let closed = false
    const connect = () => {
      setConn((c) => ({ ...c, state: 'connecting' }))
      ws = new WebSocket(`${API_URL.replace('http', 'ws')}/ws/events?token=${encodeURIComponent(API_TOKEN)}`)
      ws.onopen = () => setConn({ state: 'connected', latency: 0, retry: 0 })
      ws.onmessage = (msg) => {
        const data = JSON.parse(msg.data)
        if (data.type === 'snapshot') {
          setStatus(data.status); setSettings(data.settings); setPositions(data.positions); setOrders(data.orders); setEvents(data.events || [])
        } else if (data.type === 'event') {
          setEvents((prev) => [data.event, ...prev].slice(0, 500))
          if (data.event.category === 'SIGNAL') setSignals((prev) => [data.event.payload, ...prev].slice(0, 100))
        } else if (data.type === 'status') {
          setStatus(data.status)
        } else if (data.type === 'ping') {
          lastPingRef.current = Date.now(); ws.send(JSON.stringify({ type: 'pong' }))
        }
        if (lastPingRef.current) {
          setConn((c) => ({ ...c, latency: Date.now() - lastPingRef.current }))
        }
      }
      ws.onclose = () => {
        if (closed) return
        setConn((c) => ({ ...c, state: 'disconnected', retry: c.retry + 1 }))
        const delay = Math.min(1000 * 2 ** Math.min(conn.retry, 5), 10000)
        retryTimer = setTimeout(connect, delay)
      }
    }
    connect()
    return () => { closed = true; if (ws) ws.close(); if (retryTimer) clearTimeout(retryTimer) }
  }, [])

  const act = async (path) => {
    if (path === '/api/start') setStatus((s) => ({ ...s, running: true }))
    if (path === '/api/stop') setStatus((s) => ({ ...s, running: false }))
    await api(path, { method: 'POST' })
  }

  const filteredEvents = events.filter((e) => filter === 'ALL' || e.category === filter)

  return <div className="h-screen flex bg-bg text-text">
    <aside className="w-64 border-r border-border bg-surface flex flex-col p-4">
      <h1 className="text-lg font-bold mb-4">Trader Bot Control Center</h1>
      <nav className="space-y-2">
        {navItems.map((item) => <button key={item} onClick={() => setPage(item)} className={`w-full text-left px-3 py-2 rounded ${page===item?'bg-accent':'hover:bg-border'}`}>{item}</button>)}
      </nav>
      <div className="mt-auto text-xs text-muted space-y-1"><div>API: {API_URL}</div><div>Token: {API_TOKEN ? 'configured' : 'missing'}</div></div>
    </aside>

    <main className="flex-1 flex flex-col overflow-hidden">
      <div className="sticky top-0 z-10 bg-bg border-b border-border p-3 flex items-center gap-3 text-sm">
        <span className={`px-2 py-1 rounded ${status.running ? 'bg-success/20 text-success' : 'bg-danger/20 text-danger'}`}>{status.running ? 'RUNNING' : 'STOPPED'}</span>
        <span className="flex items-center gap-2"><span className={`w-2 h-2 rounded-full ${conn.state==='connected'?'bg-success':conn.state==='connecting'?'bg-yellow-400':'bg-danger'}`}></span>{conn.state} {conn.latency}ms</span>
        <span>Balance {status.balance?.toFixed?.(2)}</span><span>Equity {status.equity?.toFixed?.(2)}</span><span>Daily PnL {status.daily_pnl?.toFixed?.(2)}</span>
        <button onClick={async () => { const next = status.mode === 'DEMO' ? 'REAL' : 'DEMO'; await api('/api/settings', { method: 'PUT', body: JSON.stringify({ mode: next }) }); setStatus((s) => ({ ...s, mode: next })) }} className="ml-auto px-3 py-1 bg-border rounded">{status.mode}</button>
        <button onClick={() => act('/api/start')} className="px-3 py-1 bg-success/20 text-success rounded">Start</button>
        <button onClick={() => act('/api/stop')} className="px-3 py-1 bg-danger/20 text-danger rounded">Stop</button>
      </div>

      {conn.state !== 'connected' && <div className="bg-danger/20 text-danger px-4 py-2 text-sm">WebSocket disconnected. Reconnecting with backoff...</div>}

      <div className="flex-1 grid grid-cols-12 gap-3 p-3 overflow-hidden">
        <section className="col-span-4 card overflow-hidden flex flex-col">
          <div className="flex justify-between items-center mb-2"><h2 className="font-semibold">Terminal Feed</h2><button className="text-xs" onClick={() => navigator.clipboard.writeText(JSON.stringify(filteredEvents, null, 2))}>Copy all</button></div>
          <div className="flex gap-1 mb-2 flex-wrap">{logFilters.map((f) => <button key={f} onClick={() => setFilter(f)} className={`text-xs px-2 py-1 rounded ${filter===f?'bg-accent':'bg-border'}`}>{f}</button>)}</div>
          <div className="overflow-y-auto text-xs space-y-1 pr-1">{filteredEvents.map((e, i) => <details key={`${e.ts}-${i}`} className="border-b border-border pb-1"><summary>{new Date(e.ts).toLocaleTimeString()} [{e.category}] {e.message}</summary><pre className="text-muted whitespace-pre-wrap">{JSON.stringify(e.payload, null, 2)}</pre></details>)}</div>
        </section>

        <section className="col-span-5 space-y-3 overflow-y-auto">
          <div className="card"><h3 className="font-semibold mb-2">Signals</h3>{signals[0] ? <div className="text-sm">{signals[0].symbol} {signals[0].side} score {signals[0].score} reason {signals[0].reason_codes?.join(', ')}</div> : <div className="text-muted text-sm">No signals yet</div>}</div>
          <div className="card"><h3 className="font-semibold mb-2">Positions</h3><table className="w-full text-xs"><thead className="text-muted"><tr><th>Symbol</th><th>Side</th><th>Qty</th><th>Entry</th><th>PnL</th><th>Unrealized</th><th>Duration</th></tr></thead><tbody>{positions.map((p) => <tr key={p.symbol}><td>{p.symbol}</td><td>{p.side}</td><td>{p.qty}</td><td>{p.entry}</td><td>{p.pnl}</td><td>{p.unrealized}</td><td>{p.duration}s</td></tr>)}</tbody></table></div>
          <div className="card"><h3 className="font-semibold mb-2">Orders</h3><table className="w-full text-xs"><thead className="text-muted"><tr><th>Type</th><th>Price</th><th>Qty</th><th>Status</th></tr></thead><tbody>{orders.map((o) => <tr key={o.id}><td>{o.type}</td><td>{o.price}</td><td>{o.qty}</td><td>{o.status}</td></tr>)}</tbody></table></div>
          <div className="card text-sm"><h3 className="font-semibold mb-2">Risk</h3><div>max_daily_loss_pct: {settings.max_daily_loss_pct}</div><div>cooldown_seconds: {settings.cooldown_seconds}</div><div>kill_switch_engaged: {String(status.kill_switch_engaged)}</div></div>
        </section>

        <section className="col-span-3 card space-y-2">
          <h2 className="font-semibold">Operator Actions</h2>
          {[
            ['/api/start','Start','bg-success/20 text-success'],
            ['/api/stop','Stop','bg-danger/20 text-danger'],
            ['/api/pause','Pause Entries','bg-border'],
            ['/api/flatten','Flatten','bg-border'],
            ['/api/kill','Kill Switch','bg-danger/30 text-danger']
          ].map(([path,label,style]) => <button key={path} onClick={() => act(path)} className={`w-full py-2 rounded ${style}`}>{label}</button>)}
          <div className="pt-3 border-t border-border"><div className="text-xs text-muted mb-1">Presets</div><div className="grid grid-cols-2 gap-1">{['SAFE','MEDIUM','AGGRESSIVE','CUSTOM'].map((p) => <button key={p} className={`text-xs py-1 rounded ${settings.active_profile===p?'bg-accent':'bg-border'}`}>{p}</button>)}</div></div>
        </section>
      </div>
    </main>
  </div>
}

createRoot(document.getElementById('root')).render(<App />)
