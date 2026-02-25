import React, { useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
const API_TOKEN = import.meta.env.VITE_API_TOKEN || 'dev-token'
const NAV = ['TERMINAL', 'HISTORY', 'DEV', 'CONFIG']

const iconMap = {
  TERMINAL: '◫',
  HISTORY: '↺',
  DEV: '∿',
  CONFIG: '⚙',
}

function App() {
  const [route, setRoute] = useState((location.pathname.slice(1) || 'terminal').toUpperCase())
  const [status, setStatus] = useState({ running: false, mode: 'DEMO', ws_connected: false, server_time: '—', reconnecting: true })
  const [account, setAccount] = useState({ balance: '—', equity: '—', daily_pnl: '—', open_positions: 0, active_orders: 0 })
  const [positions, setPositions] = useState([])
  const [orders, setOrders] = useState([])
  const [signals, setSignals] = useState([])
  const [settings, setSettings] = useState(null)
  const [events, setEvents] = useState([])
  const [journal, setJournal] = useState([])
  const [consoleOutput, setConsoleOutput] = useState('')
  const [wsDown, setWsDown] = useState(false)

  const headers = useMemo(() => ({ 'X-API-TOKEN': API_TOKEN, 'Content-Type': 'application/json' }), [])
  const api = async (path, options = {}) => {
    const response = await fetch(`${API_URL}${path}`, { ...options, headers: { ...headers, ...(options.headers || {}) } })
    const text = await response.text()
    const json = text ? JSON.parse(text) : {}
    if (!response.ok) throw new Error(text)
    return json
  }

  const refresh = async () => {
    const [st, ac, ps, os, sg, cfg, jr] = await Promise.all([
      api('/api/status'), api('/api/account'), api('/api/positions'), api('/api/orders'), api('/api/signals?limit=100'), api('/api/settings'), api('/api/journal?page=1&limit=200'),
    ])
    setStatus(st); setAccount(ac); setPositions(ps || []); setOrders(os || []); setSignals(sg || []); setSettings(cfg); setJournal(jr.items || [])
  }

  useEffect(() => { refresh() }, [])

  useEffect(() => {
    const ws = new WebSocket(`${API_URL.replace('http', 'ws')}/ws/events?token=${encodeURIComponent(API_TOKEN)}`)
    ws.onopen = () => setWsDown(false)
    ws.onmessage = (evt) => {
      const packet = JSON.parse(evt.data)
      if (packet.type === 'INITIAL_SNAPSHOT') {
        setStatus(packet.status || {})
        setAccount(packet.account || {})
        setPositions(packet.positions || [])
        setOrders(packet.orders || [])
        setSignals(packet.signals || [])
        setSettings(packet.settings || null)
        setEvents(packet.events || [])
      }
      if (packet.type === 'EVENT') setEvents((prev) => [packet.event, ...prev].slice(0, 1500))
      if (packet.type === 'STATUS_TICK') {
        setStatus(packet.status || {})
        setAccount(packet.account || {})
      }
    }
    ws.onclose = () => setWsDown(true)
    return () => ws.close()
  }, [])

  const action = async (path, body) => {
    const payload = await api(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined })
    setConsoleOutput(JSON.stringify(payload, null, 2))
    await refresh()
  }

  const saveSettings = async () => {
    const payload = await api('/api/settings', { method: 'PUT', body: JSON.stringify(settings) })
    setSettings(payload)
    setConsoleOutput(JSON.stringify({ success: true, settings_saved: true }, null, 2))
  }

  const patchSettings = (fn) => setSettings((old) => fn(structuredClone(old)))
  const fmt = (v) => (v === null || v === undefined || v === '' ? '—' : v)

  return <div className='layout'>
    <aside className='sidebar'>
      <div className='brand'><span className='bolt'>⚡</span><b>BELEVAKU</b></div>
      <nav>{NAV.map((item) => <button key={item} className={`nav-btn ${route === item ? 'active' : ''}`} onClick={() => { history.replaceState({}, '', `/${item.toLowerCase()}`); setRoute(item) }}><span>{iconMap[item]}</span>{item}</button>)}</nav>
      <div className='sidebar-footer'>
        <div className='tiny'>ACCOUNT EQUITY</div><div className='money'>${fmt(account.equity)}</div>
        <div className='tiny'>DAILY PNL</div><div className='green'>+${fmt(account.daily_pnl)} (0.00%)</div>
      </div>
    </aside>

    <section className='main'>
      <header className='top'>
        <div className='title-wrap'>
          <h1>Belevaku Trading</h1>
          <div className='subtitle'><span className='dot amber'/>BOT: {status.running ? 'RUNNING' : 'STOPPED'}</div>
        </div>
        <div className='kpis'>
          <Kpi label='WALLET BALANCE' value={account.balance || '—'} />
          <Kpi label='OPEN POSITIONS' value={account.open_positions ?? '—'} />
          <Kpi label='ACTIVE ORDERS' value={account.active_orders ?? '—'} />
          <Kpi label='TOTAL PNL' value={account.daily_pnl || '—'} />
        </div>
        <div className='top-right'>
          <span className='binance'><span className={`dot ${status.ws_connected ? 'green' : 'red'}`}/>BINANCE: {status.ws_connected ? 'ONLINE' : 'OFFLINE'}</span>
          <button className='start-btn' onClick={() => action(status.running ? '/api/stop' : '/api/start')}>{status.running ? '■ STOP' : '▶ START'}</button>
        </div>
      </header>

      {route === 'TERMINAL' && <Terminal account={account} settings={settings} journal={journal} orders={orders} />}
      {route === 'HISTORY' && <History signals={signals} journal={journal} />}
      {route === 'DEV' && <Dev onAction={action} consoleOutput={consoleOutput} settings={settings} />}
      {route === 'CONFIG' && <Config settings={settings} patchSettings={patchSettings} saveSettings={saveSettings} />}

      <footer className='statusbar'>
        <div>VOL FILTER: {Math.round((settings?.min_quote_volume_24h || 25000000) / 1_000_000)}M &nbsp;&nbsp; EXCHANGE: BINANCE &nbsp;&nbsp; MODE: {status.mode}</div>
        <div>SERVER TIME: {status.server_time?.slice(11, 19) || '—'} &nbsp;<span className='reconnect'>{(wsDown || status.reconnecting) ? 'RECONNECTING...' : 'LIVE'}</span></div>
      </footer>
    </section>
  </div>
}

function Kpi({ label, value }) { return <div><div className='kpi-label'>{label}</div><div className='kpi-value'>{value || '—'}</div></div> }

function Terminal({ account, settings, journal, orders }) {
  return <div className='page'>
    <div className='cards-4'>
      <Card title='TOTAL BALANCE' value={`$${account.balance || '—'}`} />
      <Card title='OPEN POSITIONS' value={account.open_positions ?? 0} />
      <Card title='ACTIVE ORDERS' value={account.active_orders ?? 0} />
      <Card title='RISK SCORE' value={(settings?.active_profile || 'AGGRESSIVE').toUpperCase()} />
    </div>

    <div className='two-col'>
      <section className='panel market'><h3>Market Performance</h3><div className='chart-fake'/><div className='chart-value'>$63,842.12</div></section>
      <section className='panel active-pos'><h3>Active Position</h3><div className='empty'>NO ACTIVE POSITIONS</div></section>
    </div>

    <div className='two-col'>
      <section className='panel feed'><div className='panel-head'>Activity Feed</div><div className='feed-log'>{journal.length ? journal.map((r) => <div key={r.id}>[{(r.ts || '').slice(11, 19)}] {r.message}</div>) : <div>NO EVENTS</div>}</div></section>
      <section className='panel'><div className='panel-head'>Trade History</div><table><thead><tr><th>TIME</th><th>SYMBOL</th><th>SIDE</th><th>PRICE</th><th>SIZE</th><th>STATUS</th></tr></thead><tbody>{orders.length ? orders.map((o, i) => <tr key={i}><td>—</td><td>{o.symbol}</td><td>{o.side}</td><td>{o.price}</td><td>{o.qty}</td><td>{o.status}</td></tr>) : <tr><td colSpan={6}>NO TRADE RECORDS FOUND</td></tr>}</tbody></table></section>
    </div>
  </div>
}

function History({ signals, journal }) {
  return <div className='page'>
    <section className='panel'><div className='panel-head'>Signal History</div><table><thead><tr><th>TIME</th><th>SYMBOL</th><th>DIRECTION</th><th>CONFIDENCE</th><th>STATE</th></tr></thead><tbody>{signals.length ? signals.map((s, i) => <tr key={i}><td>{(s.ts || '').slice(11, 19)}</td><td>{s.symbol}</td><td>{s.side}</td><td>{s.confidence}</td><td>{s.state}</td></tr>) : <tr><td colSpan={5}>NO SIGNALS YET</td></tr>}</tbody></table></section>
    <section className='panel'><div className='panel-head'>System Log Archive</div><div className='feed-log'>{journal.map((r) => <div key={r.id}>[{(r.ts || '').slice(11, 19)}] [{r.category}] {r.message}</div>)}</div></section>
  </div>
}

function Dev({ onAction, consoleOutput, settings }) {
  const symbol = settings?.symbols?.[0] || 'BTCUSDT'
  return <div className='page narrow'>
    <h2>Developer Console</h2><p className='sub'>TESTING & DEBUGGING TOOLS</p>
    <div className='two-col'>
      <section className='panel'><div className='panel-head'>Trade Execution</div><button className='btn green' onClick={() => onAction('/api/dev/place-test-trade', { symbol, amount: 100, side: 'BUY' })}>▶ PLACE TEST TRADE ($100 USDT)</button><button className='btn red' onClick={() => onAction('/api/dev/cancel-test-trade', { symbol })}>■ CANCEL TEST TRADE</button></section>
      <section className='panel'><div className='panel-head'>Connectivity</div><button className='btn blue' onClick={() => onAction('/api/test-connection', { mode: settings?.mode || 'DEMO' })}>⟳ TEST BINANCE CONNECTION</button><button className='btn gray' onClick={() => onAction('/api/dev/clear-logs')}>🗑 CLEAR SYSTEM LOGS</button></section>
    </div>
    <section className='panel'><div className='panel-head'>Simulations</div><div className='row'><button className='btn amber' onClick={() => onAction('/api/dev/clear-logs')}>⚠ SIM ERROR</button><button className='btn green' onClick={() => onAction('/api/status')}>SIM SUCCESS</button></div></section>
    <section className='panel'><div className='panel-head'>Console Output</div><pre className='console'>{consoleOutput || '{\n  "ready": true\n}'}</pre></section>
  </div>
}

function Config({ settings, patchSettings, saveSettings }) {
  if (!settings) return <div className='page'><section className='panel'>Loading...</section></div>
  const demo = settings.mode === 'DEMO'
  return <div className='page narrow'>
    <h2>System Configuration</h2><p className='sub'>BELEVAKU V2.1.0 - OPERATIONAL PARAMETERS</p>
    <section className='panel'><div className='panel-head'>Exchange Connectivity</div>
      <div className='grid3'>
        <div><label>TRADING MODE</label><div className='seg'><button className={demo ? 'active' : ''} onClick={() => patchSettings((s) => { s.mode = 'DEMO'; return s })}>DEMO</button><button className={!demo ? 'active' : ''} onClick={() => patchSettings((s) => { s.mode = 'REAL'; return s })}>REAL</button></div></div>
        <div><label>MIN 24H VOLUME (MILLIONS USDT)</label><input value={Math.round((settings.min_quote_volume_24h || 0) / 1_000_000)} onChange={(e) => patchSettings((s) => { s.min_quote_volume_24h = Number(e.target.value || 0) * 1_000_000; return s })} /></div>
      </div>
    </section>

    <section className='panel'><div className='panel-head'>API Credentials</div>
      <div className='grid2'>
        <div><label>REAL API KEY</label><input value={settings.credentials?.REAL?.key || ''} onChange={(e) => patchSettings((s) => { s.credentials.REAL.key = e.target.value; return s })} /></div>
        <div><label>REAL API SECRET</label><input type='password' value={settings.credentials?.REAL?.secret || ''} onChange={(e) => patchSettings((s) => { s.credentials.REAL.secret = e.target.value; return s })} /></div>
        <div><label>DEMO API KEY (TESTNET)</label><input value={settings.credentials?.DEMO?.key || ''} onChange={(e) => patchSettings((s) => { s.credentials.DEMO.key = e.target.value; return s })} /></div>
        <div><label>DEMO API SECRET (TESTNET)</label><input type='password' value={settings.credentials?.DEMO?.secret || ''} onChange={(e) => patchSettings((s) => { s.credentials.DEMO.secret = e.target.value; return s })} /></div>
      </div>
    </section>

    <section className='panel'><div className='panel-head'>Strategy Engine</div>
      <div className='grid2'>
        <div><label>ALGORITHM</label><select value={settings.strategy?.take_profit_model || 'dynamic_retrace'} onChange={(e) => patchSettings((s) => { s.strategy.take_profit_model = e.target.value; return s })}><option value='dynamic_retrace'>Bollinger Breakout (Volatility)</option><option value='fixed'>Impulse Mean Revert</option></select></div>
        <div><label>RISK PROFILE</label><div className='seg'><button onClick={() => patchSettings((s) => { s.app_state.active_profile = 'SAFE'; return s })}>SAFE</button><button onClick={() => patchSettings((s) => { s.app_state.active_profile = 'MEDIUM'; return s })}>MEDIUM</button><button className='active' onClick={() => patchSettings((s) => { s.app_state.active_profile = 'AGGRESSIVE'; return s })}>AGGRESSIVE</button></div></div>
      </div>
    </section>

    <section className='panel'><div className='panel-head'>Risk Management</div>
      <div className='grid3'>
        <div><label>POSITION SIZE (USDT)</label><input value={settings.execution?.max_notional_per_trade || 100} onChange={(e) => patchSettings((s) => { s.risk.max_notional_per_trade = Number(e.target.value || 0); return s })} /></div>
        <div><label>STOP LOSS (%)</label><input value={settings.app_state?.max_daily_loss_pct || 2} onChange={(e) => patchSettings((s) => { s.app_state.max_daily_loss_pct = Number(e.target.value || 0); return s })} /></div>
        <div><label>TAKE PROFIT (%)</label><input value={settings.strategy?.retrace_target_pct?.[1] || 0.5} onChange={(e) => patchSettings((s) => { s.strategy.retrace_target_pct = [0.3, Number(e.target.value || 0.5), 0.6]; return s })} /></div>
      </div>
    </section>

    <div className='right'><button className='start-btn' onClick={saveSettings}>SAVE CONFIGURATION</button></div>
  </div>
}

function Card({ title, value }) { return <section className='panel metric'><div className='kpi-label'>{title}</div><div className='metric-value'>{value}</div></section> }

createRoot(document.getElementById('root')).render(<App />)
