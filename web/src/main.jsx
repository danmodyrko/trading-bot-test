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

const SETTINGS_SECTIONS = {
  root: [
    ['mode', 'select', ['DEMO', 'REAL']],
    ['exchange', 'text'],
    ['symbols', 'list'],
    ['auto_discover_symbols', 'bool'],
    ['min_quote_volume_24h', 'number'],
    ['min_trade_rate_baseline', 'number'],
    ['max_symbols_active', 'number']
  ],
  endpoints: [
    ['ws_demo', 'text'],
    ['ws_real', 'text'],
    ['rest_demo', 'text'],
    ['rest_real', 'text']
  ],
  risk: [
    ['max_daily_loss_pct', 'number'],
    ['max_trade_risk_pct', 'number'],
    ['max_positions', 'number'],
    ['max_positions_per_symbol', 'number'],
    ['max_leverage', 'number'],
    ['max_notional_per_trade', 'number'],
    ['max_exposure_per_symbol', 'number'],
    ['max_account_exposure', 'number'],
    ['max_consecutive_losses', 'number'],
    ['cooldown_seconds', 'number'],
    ['loss_cooldown_seconds', 'number'],
    ['include_unrealized_pnl', 'bool']
  ],
  strategy: [
    ['impulse_threshold_pct', 'number'],
    ['impulse_window_seconds', 'number'],
    ['volume_zscore_threshold', 'number'],
    ['trade_rate_burst_threshold', 'number'],
    ['exhaustion_ratio_threshold', 'number'],
    ['exhaustion_confidence_threshold', 'number'],
    ['vol_kill_threshold', 'number'],
    ['vol_cooldown_seconds', 'number'],
    ['regime_filter_enabled', 'bool'],
    ['trend_strength_threshold', 'number'],
    ['retrace_target_pct', 'list'],
    ['stop_loss_model', 'select', ['ATR', 'fixed']],
    ['take_profit_model', 'select', ['dynamic_retrace', 'fixed']],
    ['hard_time_stop_seconds', 'number']
  ],
  execution: [
    ['order_type', 'select', ['MARKET', 'LIMIT']],
    ['max_slippage_bps', 'number'],
    ['edge_safety_factor', 'number'],
    ['min_orderbook_depth', 'number'],
    ['spread_guard_bps', 'number'],
    ['max_retry_attempts', 'number'],
    ['retry_base_delay_s', 'number'],
    ['dry_run', 'bool'],
    ['enable_real_orders', 'bool']
  ],
  ui: [
    ['dark_mode', 'bool'],
    ['refresh_ms', 'number'],
    ['sound_notifications', 'bool']
  ],
  storage: [
    ['sqlite_path', 'text'],
    ['csv_dir', 'text'],
    ['app_state_path', 'text'],
    ['snapshots_path', 'text'],
    ['trade_journal_path', 'text']
  ],
  api: [
    ['demo_key_env', 'text'],
    ['demo_secret_env', 'text'],
    ['real_key_env', 'text'],
    ['real_secret_env', 'text']
  ]
}

const prettyNumber = (value) => Number(value || 0).toFixed(2)
const labelize = (key) => key.replaceAll('_', ' ')

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
  const [presets, setPresets] = useState({})
  const [connectionMsg, setConnectionMsg] = useState('')
  const [tradeMsg, setTradeMsg] = useState('')

  const headers = useMemo(() => ({ 'X-API-TOKEN': API_TOKEN, 'Content-Type': 'application/json' }), [])

  const api = async (path, options = {}) => {
    const response = await fetch(`${API_URL}${path}`, { ...options, headers: { ...headers, ...(options.headers || {}) } })
    if (!response.ok) throw new Error(`${path}: ${response.status}`)
    return response.json()
  }

  const loadAll = async () => {
    const [s, a, p, o, j, cfg, presetResp] = await Promise.all([
      api('/api/status'),
      api('/api/account'),
      api('/api/positions'),
      api('/api/orders'),
      api('/api/journal?page=1&page_size=100'),
      api('/api/settings'),
      api('/api/presets')
    ])
    setStatus(s)
    setAccount(a)
    setPositions(Array.isArray(p) ? p : [])
    setOrders(Array.isArray(o) ? o : [])
    setJournal(j.items || [])
    setSettings(cfg)
    setPresets(presetResp.presets || {})
  }

  useEffect(() => { loadAll() }, [])
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
        if (data.type === 'status') return setStatus(data.status)
        if (data.type === 'event') setEvents((prev) => [data.event, ...prev].slice(0, 1000))
      }
      ws.onclose = () => { reconnect = setTimeout(connect, 1000) }
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

  const testConnection = async (mode) => {
    setConnectionMsg(`Testing ${mode} connection...`)
    try {
      const result = await api('/api/test-connection', { method: 'POST', body: JSON.stringify({ mode }) })
      setConnectionMsg(result.ok ? `Connected (${result.mode}) latency ${result.latency_ms}ms` : `Connection failed: ${result.message || 'unknown error'}`)
    } catch (error) {
      setConnectionMsg(`Connection failed: ${error.message}`)
    }
  }

  const applyPreset = (presetName) => {
    const preset = presets[presetName]
    if (!preset) return
    setSettings((prev) => ({
      ...prev,
      risk: {
        ...(prev.risk || {}),
        max_positions: preset.max_positions,
        max_daily_loss_pct: preset.max_daily_loss_pct,
        max_leverage: preset.max_leverage,
        max_trade_risk_pct: preset.max_trade_risk_pct
      },
      execution: {
        ...(prev.execution || {}),
        max_slippage_bps: preset.max_slippage_bps,
        spread_guard_bps: preset.spread_guard_bps,
        edge_safety_factor: preset.edge_gate_factor
      },
      strategy: {
        ...(prev.strategy || {}),
        impulse_threshold_pct: preset.impulse_threshold_pct,
        impulse_window_seconds: preset.impulse_window_seconds,
        exhaustion_ratio_threshold: preset.exhaustion_ratio_threshold,
        trend_strength_threshold: preset.trend_strength_threshold,
        hard_time_stop_seconds: preset.time_stop_seconds,
        stop_loss_model: preset.stop_model,
        retrace_target_pct: preset.tp_profile
      }
    }))
  }

  const placeTestTrade = async () => {
    const symbol = settings.symbols?.[0] || 'BTCUSDT'
    setTradeMsg(`Submitting $1 test trade on ${symbol}...`)
    try {
      const result = await api('/api/test-trade', { method: 'POST', body: JSON.stringify({ symbol, side: 'BUY', quote_value_usdt: 1.0 }) })
      setTradeMsg(result.ok ? `Test trade sent: ${result.symbol} qty ${result.quantity}` : `Test trade failed: ${result.message || 'unknown error'}`)
      await loadAll()
    } catch (error) {
      setTradeMsg(`Test trade failed: ${error.message}`)
    }
  }

  const updateRoot = (key, value) => setSettings((prev) => ({ ...prev, [key]: value }))
  const updateNested = (section, key, value) => setSettings((prev) => ({ ...prev, [section]: { ...(prev[section] || {}), [key]: value } }))

  const renderField = (section, key, kind, options) => {
    const current = section === 'root' ? settings[key] : settings[section]?.[key]
    const onChangeValue = (value) => {
      if (section === 'root') updateRoot(key, value)
      else updateNested(section, key, value)
    }

    if (kind === 'bool') {
      return <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={Boolean(current)} onChange={(e) => onChangeValue(e.target.checked)} /> {labelize(key)}</label>
    }

    if (kind === 'select') {
      return <label>{labelize(key)}
        <select value={current || options[0]} onChange={(e) => onChangeValue(e.target.value)}>
          {options.map((opt) => <option key={opt} value={opt}>{opt}</option>)}
        </select>
      </label>
    }

    if (kind === 'list') {
      return <label>{labelize(key)}
        <input value={Array.isArray(current) ? current.join(', ') : ''} onChange={(e) => onChangeValue(e.target.value.split(',').map((x) => x.trim()).filter(Boolean))} placeholder="comma,separated,values" />
      </label>
    }

    if (kind === 'number') {
      return <label>{labelize(key)}
        <input type="number" value={current ?? ''} onChange={(e) => onChangeValue(e.target.value === '' ? '' : Number(e.target.value))} />
      </label>
    }

    return <label>{labelize(key)}<input value={current ?? ''} onChange={(e) => onChangeValue(e.target.value)} /></label>
  }

  const filteredEvents = events.filter((evt) => filter === 'ALL' || evt.category === filter || evt.level === filter)

  return <div className="min-h-screen flex bg-bg text-text">
    <aside className="w-64 border-r border-border bg-surface/90 backdrop-blur flex flex-col p-5 gap-6">
      <div><p className="text-xs uppercase text-text-muted tracking-[0.2em]">Trading Bot</p><h1 className="text-xl font-bold">Control Center</h1></div>
      <nav className="space-y-2">{routes.map((item) => <button key={item.path} onClick={() => navigate(item.path)} className={`nav-btn ${route === item.path ? 'nav-btn-active' : 'nav-btn-idle'}`}>{item.label}</button>)}</nav>
      <div className="text-xs text-text-muted mt-auto space-y-1"><div>API: {API_URL}</div><div>Mode: {status.mode || 'DEMO'}</div></div>
    </aside>

    <main className="flex-1 p-5 overflow-auto space-y-4">
      <SectionCard title="Bot controls" subtitle="Quick actions with live health indicators.">
        <div className="flex flex-wrap gap-2 items-center text-sm">
          <StatusBadge active={status.running} activeText="Running" idleText="Stopped" />
          <StatusBadge active={status.ws_connected} activeText="Realtime connected" idleText="Realtime offline" />
          <span className="metric-chip">Latency: {status.latency_ms}ms</span><span className="metric-chip">Uptime: {status.uptime_seconds}s</span>
          <span className="metric-chip">Balance: {prettyNumber(account.balance)}</span><span className="metric-chip">Equity: {prettyNumber(account.equity)}</span>
        </div>
        <div className="flex flex-wrap gap-2 mt-3">
          <button onClick={() => act('/api/start')} className="action-btn action-good">Start</button>
          <button onClick={() => act('/api/stop')} className="action-btn action-bad">Stop</button>
          <button onClick={() => act('/api/pause')} className="action-btn">Pause</button>
          <button onClick={() => act('/api/resume')} className="action-btn">Resume</button>
          <button onClick={() => act('/api/flatten')} className="action-btn">Flatten</button>
          <button onClick={() => act('/api/kill')} className="action-btn action-bad">Emergency Kill</button>
          <button onClick={placeTestTrade} className="action-btn">Test Trade ($1)</button>
        </div>
        {tradeMsg && <p className="text-xs text-text-muted mt-2">{tradeMsg}</p>}
      </SectionCard>

      {route === '/dashboard' && <div className="grid xl:grid-cols-3 gap-4">
        <SectionCard title="Live events" subtitle="Use filters to focus on warnings, risk, or order activity.">
          <div className="flex gap-1 mb-3 flex-wrap">{eventFilters.map((f) => <button key={f} className={`chip ${filter === f ? 'chip-active' : ''}`} onClick={() => setFilter(f)}>{f}</button>)}</div>
          <div className="text-xs space-y-2 max-h-[420px] overflow-y-auto pr-1">
            {filteredEvents.map((e, idx) => <div key={`${e.ts}-${idx}`} className="event-row"><p className="text-text-muted">{e.ts}</p><p>[{e.category}/{e.level}] {e.message}</p></div>)}
            {filteredEvents.length === 0 && <p className="text-text-muted">No events in this category yet.</p>}
          </div>
        </SectionCard>
        <SectionCard title="Portfolio summary" subtitle="Current account and activity snapshot."><dl className="stats-grid"><div><dt>Mode</dt><dd>{status.mode}</dd></div><div><dt>Open positions</dt><dd>{positions.length}</dd></div><div><dt>Open orders</dt><dd>{orders.length}</dd></div><div><dt>Journal rows</dt><dd>{journal.length}</dd></div></dl></SectionCard>
        <SectionCard title="Next step" subtitle="Connect API credentials in environment variables named in the API section."><p className="text-sm text-text-muted leading-relaxed">V2 now exposes the full backend settings surface from V1-compatible config blocks and keeps action buttons wired to live API endpoints.</p></SectionCard>
      </div>}

      {route === '/positions' && <SectionCard title="Positions" subtitle="Readable table of active positions."><div className="table-wrap"><table className="data-table"><thead><tr><th>Symbol</th><th>Side</th><th>Qty</th><th>Entry</th><th>Mark</th><th>PnL</th></tr></thead><tbody>{positions.map((row, idx) => <tr key={`${row.symbol || 'row'}-${idx}`}><td>{row.symbol || '-'}</td><td>{row.side || '-'}</td><td>{row.qty ?? '-'}</td><td>{row.entry_price ?? '-'}</td><td>{row.mark_price ?? '-'}</td><td>{row.pnl ?? '-'}</td></tr>)}{positions.length === 0 && <tr><td colSpan="6" className="text-center text-text-muted">No open positions</td></tr>}</tbody></table></div></SectionCard>}
      {route === '/orders' && <SectionCard title="Orders" subtitle="Latest order activity."><div className="table-wrap"><table className="data-table"><thead><tr><th>Symbol</th><th>Type</th><th>Side</th><th>Qty</th><th>Price</th><th>Status</th></tr></thead><tbody>{orders.map((row, idx) => <tr key={`${row.id || 'order'}-${idx}`}><td>{row.symbol || '-'}</td><td>{row.type || '-'}</td><td>{row.side || '-'}</td><td>{row.qty ?? '-'}</td><td>{row.price ?? '-'}</td><td>{row.status || '-'}</td></tr>)}{orders.length === 0 && <tr><td colSpan="6" className="text-center text-text-muted">No open orders</td></tr>}</tbody></table></div></SectionCard>}
      {route === '/journal' && <SectionCard title="Journal" subtitle="Recent actions and decision logs."><div className="table-wrap"><table className="data-table"><thead><tr><th>Time</th><th>Action</th><th>Details</th></tr></thead><tbody>{journal.map((row, idx) => <tr key={`${row.ts || 'journal'}-${idx}`}><td>{row.ts || '-'}</td><td>{row.action || row.type || '-'}</td><td>{row.message || JSON.stringify(row)}</td></tr>)}{journal.length === 0 && <tr><td colSpan="3" className="text-center text-text-muted">Journal is empty</td></tr>}</tbody></table></div></SectionCard>}

      {route === '/settings' && <div className="space-y-4">
        <SectionCard title="Connection & Safety" subtitle="V1 parity controls for mode, endpoints, and connection testing.">
          <div className="form-grid">{SETTINGS_SECTIONS.root.map(([k, t, o]) => <div key={`root-${k}`}>{renderField('root', k, t, o)}</div>)}</div>
          <div className="form-grid mt-3">{SETTINGS_SECTIONS.endpoints.map(([k, t, o]) => <div key={`end-${k}`}>{renderField('endpoints', k, t, o)}</div>)}</div>
          <div className="flex gap-2 mt-4 flex-wrap">
            <button onClick={() => testConnection('DEMO')} className="action-btn">Test DEMO</button>
            <button onClick={() => testConnection('REAL')} className="action-btn">Test REAL</button>
            <button onClick={saveSettings} className="action-btn action-good" disabled={saving}>{saving ? 'Saving...' : 'Save Settings'}</button>
          </div>
          {connectionMsg && <p className="text-xs text-text-muted mt-2">{connectionMsg}</p>}
          <p className="text-xs text-text-muted mt-2">Set real API key/secret in environment variables configured below.</p>
        </SectionCard>

        <SectionCard title="Presets" subtitle="Apply V1 risk presets then save."><div className="flex gap-2 flex-wrap">{Object.keys(presets).map((name) => <button key={name} onClick={() => applyPreset(name)} className="chip">{name}</button>)}</div></SectionCard>

        {Object.entries(SETTINGS_SECTIONS).filter(([section]) => !['root', 'endpoints'].includes(section)).map(([section, fields]) => (
          <SectionCard key={section} title={section.toUpperCase()} subtitle={`Editable ${section} configuration from the bot config model.`}>
            <div className="form-grid">{fields.map(([k, t, o]) => <div key={`${section}-${k}`}>{renderField(section, k, t, o)}</div>)}</div>
          </SectionCard>
        ))}
      </div>}
    </main>
  </div>
}

createRoot(document.getElementById('root')).render(<App />)
