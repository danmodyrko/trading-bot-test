import React, { useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { TOKENS } from './theme/tokens'
import './index.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
const API_TOKEN = import.meta.env.VITE_API_TOKEN || 'dev-token'
const routes = ['Dashboard', 'Positions', 'Orders', 'Journal', 'Settings']
const filters = ['ALL', 'INFO', 'WARNING', 'ERROR', 'SYSTEM', 'ORDER', 'RISK']

function App() {
  const [route, setRoute] = useState(location.pathname === '/' ? 'Dashboard' : location.pathname.slice(1).replace(/^\w/, (c) => c.toUpperCase()))
  const [status, setStatus] = useState({ running: false, mode: 'DEMO', ws_connected: false, latency: 0, uptime: 0 })
  const [account, setAccount] = useState({ balance: 'N/A', equity: 'N/A', daily_pnl: 'N/A', reason: '' })
  const [positions, setPositions] = useState([])
  const [orders, setOrders] = useState([])
  const [signals, setSignals] = useState([])
  const [risk, setRisk] = useState({})
  const [settings, setSettings] = useState({})
  const [journal, setJournal] = useState([])
  const [events, setEvents] = useState([])
  const [eventFilter, setEventFilter] = useState('ALL')
  const [banner, setBanner] = useState('')

  const headers = useMemo(() => ({ 'X-API-TOKEN': API_TOKEN, 'Content-Type': 'application/json' }), [])
  const api = async (path, opts = {}) => {
    const response = await fetch(`${API_URL}${path}`, { ...opts, headers: { ...headers, ...(opts.headers || {}) } })
    if (!response.ok) throw new Error(await response.text())
    return response.json()
  }

  const refresh = async () => {
    const [s, a, p, o, g, r, cfg, j] = await Promise.all([
      api('/api/status'), api('/api/account'), api('/api/positions'), api('/api/orders'), api('/api/signals'), api('/api/risk'), api('/api/settings'), api('/api/journal?page=1&limit=100')
    ])
    setStatus(s); setAccount(a); setPositions(p); setOrders(o); setSignals(g); setRisk(r); setSettings(cfg); setJournal(j.items || [])
  }
  useEffect(() => { refresh() }, [])

  useEffect(() => {
    const ws = new WebSocket(`${API_URL.replace('http', 'ws')}/ws/events?token=${encodeURIComponent(API_TOKEN)}`)
    ws.onmessage = (m) => {
      const d = JSON.parse(m.data)
      if (d.type === 'INITIAL_SNAPSHOT') {
        setStatus(d.status); setAccount(d.account); setPositions(d.positions || []); setOrders(d.orders || []); setSignals(d.signals || []); setRisk(d.risk || {}); setSettings(d.settings || {}); setEvents(d.events || []); setBanner('')
      } else if (d.type === 'EVENT') setEvents((prev) => [d.event, ...prev].slice(0, 2000))
      else if (d.type === 'STATUS_TICK') { setStatus(d.status); setAccount(d.account) }
    }
    ws.onclose = () => setBanner('WebSocket disconnected; attempting REST only.')
    return () => ws.close()
  }, [])

  const go = (name) => { history.pushState({}, '', `/${name.toLowerCase()}`); setRoute(name) }
  const act = async (path, body = null) => { await api(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined }); refresh() }
  const saveSettings = async () => { await api('/api/settings', { method: 'PUT', body: JSON.stringify(settings) }); refresh() }
  const setField = (section, key, value) => setSettings((s) => ({ ...s, [section]: { ...(s[section] || {}), [key]: value } }))
  const applyPreset = (name) => act(`/api/preset/${name.toLowerCase()}`)

  const fields = settings?.app_state ? Object.keys(settings.app_state) : []
  const shownEvents = events.filter((e) => eventFilter === 'ALL' || e.level === eventFilter || e.category === eventFilter)

  return <div className='app' style={{ '--bg': TOKENS.PRIMARY_BG, '--border': TOKENS.BORDER, '--txt': TOKENS.TEXT_MAIN, '--muted': TOKENS.TEXT_MUTED, '--blue': TOKENS.ACCENT_BLUE, '--red': TOKENS.ACCENT_RED, '--green': TOKENS.ACCENT_GREEN, '--gold': TOKENS.ACCENT_GOLD }}>
    <aside className='sidebar'>{routes.map((r) => <button key={r} className={`btn nav ${route === r ? 'active' : ''}`} onClick={() => go(r)}>{r}</button>)}</aside>
    <main className='main'>
      {banner && <div className='banner'>{banner}</div>}
      <section className='card row'>
        <span className='pill'>{status.running ? 'RUNNING' : 'STOPPED'}</span>
        <span className='pill'>{status.mode}</span><span className='pill'>{status.ws_connected ? 'CONNECTED' : 'DISCONNECTED'}</span>
        <button className='btn' onClick={() => act('/api/start')}>Start</button><button className='btn' onClick={() => act('/api/stop')}>Stop</button>
        <button className='btn' onClick={() => act('/api/pause')}>Pause</button><button className='btn' onClick={() => act('/api/resume')}>Resume</button>
        <button className='btn' onClick={() => act('/api/flatten')}>Flatten</button><button className='btn danger' onClick={() => act('/api/kill')}>Kill</button>
      </section>
      {route === 'Dashboard' && <>
        <section className='row'>
          <div className='card metric'><h4>Balance</h4><b>{account.balance}</b></div>
          <div className='card metric'><h4>Equity</h4><b>{account.equity}</b></div>
          <div className='card metric'><h4>Daily PnL</h4><b>{account.daily_pnl}</b></div>
        </section>
        <section className='card'><h3>Presets</h3><div className='row'><button className='btn' onClick={() => applyPreset('safe')}>Safe</button><button className='btn' onClick={() => applyPreset('medium')}>Medium</button><button className='btn' onClick={() => applyPreset('aggressive')}>Aggressive</button><span className='pill'>Profile: {settings?.active_profile || risk.active_profile || 'CUSTOM'}</span></div></section>
        <section className='card'><h3>Live log</h3><div className='row'>{filters.map((f) => <button key={f} className='btn' onClick={() => setEventFilter(f)}>{f}</button>)}<button className='btn' onClick={() => navigator.clipboard.writeText(shownEvents.map((e) => `${e.ts} ${e.category} ${e.message}`).join('\n'))}>Copy</button></div><div className='log'>{shownEvents.slice(0, 200).map((e, i) => <div key={i}>{e.ts} [{e.category}] {e.message}</div>)}</div></section>
      </>}
      {route === 'Positions' && <Table title='Positions' rows={positions} cols={['symbol', 'side', 'qty', 'entry_price', 'mark_price', 'pnl']} />}
      {route === 'Orders' && <Table title='Orders' rows={orders} cols={['id', 'symbol', 'type', 'side', 'qty', 'price', 'status']} />}
      {route === 'Journal' && <Table title='Journal' rows={journal} cols={['ts', 'severity', 'category', 'symbol', 'message']} />}
      {route === 'Settings' && <section className='card'><h3>Settings</h3><div className='row'><button className='btn' onClick={() => act('/api/test-connection', { mode: 'DEMO' })}>Test DEMO</button><button className='btn' onClick={() => act('/api/test-connection', { mode: 'REAL' })}>Test REAL</button><button className='btn good' onClick={saveSettings}>Save</button></div><div className='form'>{Object.keys(settings).filter((k) => typeof settings[k] === 'object' && k !== 'app_state').map((section) => <div key={section} className='card'><h4>{section}</h4>{Object.entries(settings[section]).map(([k, v]) => <label key={k}>{k}<input value={Array.isArray(v) ? v.join(',') : String(v)} onChange={(e) => setField(section, k, e.target.value)} /></label>)}</div>)}{fields.length > 0 && <div className='card'><h4>app_state</h4>{fields.map((k) => <label key={k}>{k}<input value={String(settings.app_state[k])} onChange={(e) => setSettings((s) => ({ ...s, app_state: { ...(s.app_state || {}), [k]: e.target.value } }))} /></label>)}</div>}</div></section>}
      <section className='card'><h3>Signals</h3><Table rows={signals} cols={['ts', 'symbol', 'state', 'confidence', 'side', 'reasons']} /></section>
    </main>
  </div>
}

function Table({ title, rows = [], cols = [] }) {
  return <section className='card'><h3>{title}</h3><table><thead><tr>{cols.map((c) => <th key={c}>{c}</th>)}</tr></thead><tbody>{rows.length ? rows.map((r, i) => <tr key={i}>{cols.map((c) => <td key={c}>{r[c] ?? 'N/A'}</td>)}</tr>) : <tr><td colSpan={cols.length || 1}>N/A</td></tr>}</tbody></table></section>
}

createRoot(document.getElementById('root')).render(<App />)
