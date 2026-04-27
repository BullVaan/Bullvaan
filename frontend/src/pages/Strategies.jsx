import { useEffect, useState, useCallback } from 'react';
import { API_BASE_URL } from '../utils/api';
import { getAuthHeaders } from '../utils/auth';

const INDICES = [
  { label: 'NIFTY 50', key: '^NSEI' },
  { label: 'BANK NIFTY', key: '^NSEBANK' },
  { label: 'SENSEX', key: '^BSESN' }
];

const SIGNAL_STYLE = {
  BUY: { bg: '#052e16', border: '#16a34a', color: '#4ade80', dot: '#22c55e' },
  SELL: { bg: '#2d0a0a', border: '#dc2626', color: '#f87171', dot: '#ef4444' },
  NEUTRAL: {
    bg: '#1e293b',
    border: '#475569',
    color: '#94a3b8',
    dot: '#64748b'
  }
};

const TABS = ['Live Signals', '7-Day History'];

export default function Strategies() {
  const [selectedIndex, setSelectedIndex] = useState('^NSEI');
  const [tab, setTab] = useState('Live Signals');
  const [liveData, setLiveData] = useState(null);
  const [historyData, setHistoryData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [histLoading, setHistLoading] = useState(false);
  const [error, setError] = useState('');
  const [lastUpdated, setLastUpdated] = useState(null);

  // ── Fetch live signals ──────────────────────────────────────────
  const fetchLive = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const res = await fetch(
        `${API_BASE_URL}/signals?symbol=${selectedIndex}&timeframe=5m`,
        { headers: getAuthHeaders() }
      );
      const data = await res.json();
      if (data?.error) {
        setError(data.message || data.error);
        return;
      }
      setLiveData(data);
      setLastUpdated(new Date());
    } catch {
      setError('Cannot connect to backend');
    } finally {
      setLoading(false);
    }
  }, [selectedIndex]);

  // ── Fetch history ──────────────────────────────────────────────
  const fetchHistory = useCallback(async () => {
    try {
      setHistLoading(true);
      const res = await fetch(
        `${API_BASE_URL}/strategy-history?symbol=${selectedIndex}&days=7`,
        { headers: getAuthHeaders() }
      );
      const data = await res.json();
      setHistoryData(data?.rows || []);
    } catch {
      setHistoryData([]);
    } finally {
      setHistLoading(false);
    }
  }, [selectedIndex]);

  useEffect(() => {
    fetchLive();
  }, [fetchLive]);

  useEffect(() => {
    if (tab === '7-Day History') fetchHistory();
  }, [tab, fetchHistory]);

  // Auto-refresh live every 30s
  useEffect(() => {
    if (tab !== 'Live Signals') return;
    const t = setInterval(fetchLive, 30000);
    return () => clearInterval(t);
  }, [tab, fetchLive]);

  // ── Compute per-strategy 7-day accuracy using outcome column ─────
  const accuracy = (() => {
    if (!historyData.length) return {};
    const byStrategy = {};
    historyData.forEach((row) => {
      const k = row.strategy;
      if (!byStrategy[k])
        byStrategy[k] = {
          correct: 0,
          wrong: 0,
          neutral_skip: 0,
          total: 0,
          judged: 0
        };
      byStrategy[k].total++;
      if (row.outcome === 'CORRECT') {
        byStrategy[k].correct++;
        byStrategy[k].judged++;
      } else if (row.outcome === 'WRONG') {
        byStrategy[k].wrong++;
        byStrategy[k].judged++;
      } else if (row.outcome === 'NEUTRAL_SKIP') byStrategy[k].neutral_skip++;
      // rows with no outcome yet are still counted in total
    });
    return byStrategy;
  })();

  const indexLabel = INDICES.find((i) => i.key === selectedIndex)?.label || '';
  const allSignals = liveData?.signals || [];
  const consensus = liveData?.consensus || 'NEUTRAL';
  const price = liveData?.price;

  return (
    <div style={{ padding: '24px', color: '#e2e8f0', minHeight: '100vh' }}>
      {/* ── Header ── */}
      <div style={{ marginBottom: 24 }}>
        <h1
          style={{ fontSize: 22, fontWeight: 700, color: '#f8fafc', margin: 0 }}
        >
          Strategy Monitor
        </h1>
        <p style={{ color: '#64748b', marginTop: 4, fontSize: 14 }}>
          Live signals &amp; 7-day performance per strategy
        </p>
      </div>

      {/* ── Index selector ── */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
        {INDICES.map((idx) => (
          <button
            key={idx.key}
            onClick={() => {
              setSelectedIndex(idx.key);
              setLiveData(null);
              setHistoryData([]);
            }}
            style={{
              padding: '8px 20px',
              borderRadius: 8,
              border:
                selectedIndex === idx.key
                  ? '1px solid #f97316'
                  : '1px solid #334155',
              background: selectedIndex === idx.key ? '#431407' : '#0f172a',
              color: selectedIndex === idx.key ? '#fb923c' : '#94a3b8',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: 13
            }}
          >
            {idx.label}
          </button>
        ))}
      </div>

      {/* ── Tabs ── */}
      <div
        style={{
          display: 'flex',
          gap: 4,
          marginBottom: 20,
          borderBottom: '1px solid #1e293b'
        }}
      >
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              padding: '8px 20px',
              background: 'none',
              border: 'none',
              borderBottom:
                tab === t ? '2px solid #f97316' : '2px solid transparent',
              color: tab === t ? '#fb923c' : '#64748b',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: 14,
              marginBottom: -1
            }}
          >
            {t}
          </button>
        ))}
      </div>

      {/* ══════════════════════════════════════════
          TAB: LIVE SIGNALS
      ══════════════════════════════════════════ */}
      {tab === 'Live Signals' && (
        <>
          {/* Status bar */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 16,
              marginBottom: 20
            }}
          >
            {price && (
              <span style={{ color: '#f8fafc', fontWeight: 700, fontSize: 18 }}>
                {indexLabel} &nbsp;₹{price.toLocaleString('en-IN')}
              </span>
            )}
            <SignalBadge signal={consensus} label={`Overall: ${consensus}`} />
            <button
              onClick={fetchLive}
              disabled={loading}
              style={{
                marginLeft: 'auto',
                padding: '6px 16px',
                borderRadius: 6,
                border: '1px solid #334155',
                background: '#1e293b',
                color: '#94a3b8',
                cursor: loading ? 'not-allowed' : 'pointer',
                fontSize: 13
              }}
            >
              {loading ? 'Refreshing…' : '↻ Refresh'}
            </button>
            {lastUpdated && (
              <span style={{ color: '#475569', fontSize: 12 }}>
                {lastUpdated.toLocaleTimeString()}
              </span>
            )}
          </div>

          {error && (
            <div
              style={{
                background: '#2d0a0a',
                border: '1px solid #dc2626',
                borderRadius: 8,
                padding: 12,
                color: '#f87171',
                marginBottom: 16
              }}
            >
              {error}
            </div>
          )}

          {loading && !liveData && (
            <div style={{ color: '#64748b', textAlign: 'center', padding: 40 }}>
              Loading strategies…
            </div>
          )}

          {/* Strategy cards grid */}
          {allSignals.length > 0 && (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
                gap: 16
              }}
            >
              {allSignals.map((s) => (
                <StrategyCard
                  key={s.name}
                  name={s.name}
                  signal={s.signal}
                  acc={accuracy[s.name]}
                />
              ))}
            </div>
          )}
        </>
      )}

      {/* ══════════════════════════════════════════
          TAB: 7-DAY HISTORY
      ══════════════════════════════════════════ */}
      {tab === '7-Day History' && (
        <>
          {histLoading && (
            <div style={{ color: '#64748b', textAlign: 'center', padding: 40 }}>
              Loading history…
            </div>
          )}
          {!histLoading && historyData.length === 0 && (
            <div
              style={{
                background: '#0f172a',
                border: '1px solid #1e293b',
                borderRadius: 12,
                padding: 40,
                textAlign: 'center',
                color: '#475569'
              }}
            >
              <div style={{ fontSize: 32, marginBottom: 8 }}>📊</div>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>
                No history yet
              </div>
              <div style={{ fontSize: 13 }}>
                Signals are logged every 5 minutes during market hours.
                <br />
                Come back after market opens to see data here.
              </div>
            </div>
          )}
          {!histLoading && Object.keys(accuracy).length > 0 && (
            <>
              <p style={{ color: '#64748b', fontSize: 13, marginBottom: 16 }}>
                Showing last 7 days · {historyData.length} data points ·{' '}
                {indexLabel}
              </p>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
                  gap: 16
                }}
              >
                {Object.entries(accuracy).map(([name, stats]) => (
                  <AccuracyCard key={name} name={name} stats={stats} />
                ))}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}

// ── Sub-components ──────────────────────────────────────────────

function SignalBadge({ signal, label }) {
  const s = SIGNAL_STYLE[signal] || SIGNAL_STYLE.NEUTRAL;
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '4px 12px',
        borderRadius: 20,
        background: s.bg,
        border: `1px solid ${s.border}`,
        color: s.color,
        fontWeight: 700,
        fontSize: 13
      }}
    >
      <span
        style={{ width: 8, height: 8, borderRadius: '50%', background: s.dot }}
      />
      {label || signal}
    </span>
  );
}

function StrategyCard({ name, signal, acc }) {
  const s = SIGNAL_STYLE[signal] || SIGNAL_STYLE.NEUTRAL;
  const accuracyPct =
    acc && acc.judged > 0 ? Math.round((acc.correct / acc.judged) * 100) : null;
  const accColor =
    accuracyPct === null
      ? '#64748b'
      : accuracyPct >= 60
        ? '#22c55e'
        : accuracyPct >= 45
          ? '#f59e0b'
          : '#ef4444';
  return (
    <div
      style={{
        background: '#0f172a',
        border: `1px solid ${s.border}`,
        borderRadius: 12,
        padding: '16px',
        display: 'flex',
        flexDirection: 'column',
        gap: 10
      }}
    >
      <div style={{ fontSize: 13, color: '#94a3b8', fontWeight: 600 }}>
        {name}
      </div>
      <SignalBadge signal={signal} />
      {acc && (
        <div style={{ fontSize: 12, marginTop: 4 }}>
          {accuracyPct !== null ? (
            <span style={{ color: accColor, fontWeight: 700 }}>
              {accuracyPct}% accurate
            </span>
          ) : (
            <span style={{ color: '#475569' }}>outcomes pending…</span>
          )}
          <span style={{ color: '#334155', marginLeft: 6 }}>
            ({acc.judged}/{acc.total} judged)
          </span>
        </div>
      )}
    </div>
  );
}

function AccuracyCard({ name, stats }) {
  const { correct, wrong, neutral_skip, total, judged } = stats;
  const accuracyPct = judged > 0 ? Math.round((correct / judged) * 100) : null;
  const correctPct = total ? Math.round((correct / total) * 100) : 0;
  const wrongPct = total ? Math.round((wrong / total) * 100) : 0;
  const skipPct = total ? Math.round((neutral_skip / total) * 100) : 0;
  const pendingPct = total
    ? Math.round(((total - judged - neutral_skip) / total) * 100)
    : 0;
  const accColor =
    accuracyPct === null
      ? '#64748b'
      : accuracyPct >= 60
        ? '#22c55e'
        : accuracyPct >= 45
          ? '#f59e0b'
          : '#ef4444';
  return (
    <div
      style={{
        background: '#0f172a',
        border: '1px solid #1e293b',
        borderRadius: 12,
        padding: 16
      }}
    >
      <div
        style={{
          fontSize: 13,
          color: '#94a3b8',
          fontWeight: 600,
          marginBottom: 8
        }}
      >
        {name}
      </div>

      {/* Big accuracy number */}
      <div style={{ marginBottom: 12 }}>
        {accuracyPct !== null ? (
          <span style={{ fontSize: 28, fontWeight: 800, color: accColor }}>
            {accuracyPct}%
          </span>
        ) : (
          <span style={{ fontSize: 14, color: '#475569' }}>
            No outcomes yet
          </span>
        )}
        <span style={{ fontSize: 11, color: '#475569', marginLeft: 8 }}>
          {judged} judged / {total} total
        </span>
      </div>

      {/* Bars */}
      <BarRow
        label="CORRECT"
        pct={correctPct}
        count={correct}
        color="#22c55e"
      />
      <BarRow label="WRONG" pct={wrongPct} count={wrong} color="#ef4444" />
      <BarRow
        label="NEUTRAL (skipped)"
        pct={skipPct}
        count={neutral_skip}
        color="#64748b"
      />
      {pendingPct > 0 && (
        <BarRow
          label="PENDING"
          pct={pendingPct}
          count={total - judged - neutral_skip}
          color="#334155"
        />
      )}
    </div>
  );
}

function BarRow({ label, pct, count, color }) {
  return (
    <div style={{ marginBottom: 6 }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: 11,
          color: '#94a3b8',
          marginBottom: 2
        }}
      >
        <span>{label}</span>
        <span>
          {count} ({pct}%)
        </span>
      </div>
      <div style={{ background: '#1e293b', borderRadius: 4, height: 6 }}>
        <div
          style={{
            width: `${pct}%`,
            background: color,
            borderRadius: 4,
            height: 6,
            transition: '0.4s'
          }}
        />
      </div>
    </div>
  );
}
