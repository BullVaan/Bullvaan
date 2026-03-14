import { useEffect, useState } from 'react';
import { TrendingUp, TrendingDown, AlertCircle, RefreshCw } from 'lucide-react';

export default function NextMove() {
  const [predictions, setPredictions] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [error, setError] = useState(null);

  const fetchPredictions = async () => {
    setLoading(true);
    try {
      const response = await fetch('/next-move');
      const data = await response.json();

      if (data.error) {
        setError(data.error);
      } else {
        setPredictions(data.data);
        setLastUpdate(new Date());
        setError(null);
      }
    } catch (err) {
      setError(`Failed to fetch predictions: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPredictions();
    // Auto-refresh every 2 minutes
    const interval = setInterval(fetchPredictions, 120000);
    return () => clearInterval(interval);
  }, []);

  const getSignalColor = (probability) => {
    if (probability >= 68) return '#10b981'; // Green - Bullish
    if (probability >= 62) return '#f59e0b'; // Yellow - Mixed
    return '#ef4444'; // Red - Bearish
  };

  const getRecommendationBg = (color) => {
    switch (color) {
      case 'green':
        return '#065f46';
      case 'red':
        return '#7f1d1d';
      case 'yellow':
        return '#78350f';
      default:
        return '#1e293b';
    }
  };

  return (
    <div style={containerStyle}>
      <div style={headerStyle}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <TrendingUp size={24} style={{ color: '#3b82f6' }} />
          <h1 style={{ fontSize: 28, fontWeight: 700, margin: 0 }}>
            Next Move Prediction
          </h1>
        </div>
        <button
          onClick={fetchPredictions}
          disabled={loading}
          style={{
            padding: '8px 16px',
            borderRadius: 6,
            border: 'none',
            background: '#3b82f6',
            color: 'white',
            cursor: loading ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            opacity: loading ? 0.6 : 1
          }}
        >
          <RefreshCw
            size={18}
            style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }}
          />
          Refresh
        </button>
      </div>

      {lastUpdate && (
        <div style={{ color: '#94a3b8', fontSize: 12, marginBottom: 16 }}>
          Last updated: {lastUpdate.toLocaleTimeString()}
        </div>
      )}

      {error && (
        <div style={errorStyle}>
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
      )}

      {loading ? (
        <div style={{ textAlign: 'center', padding: '40px', color: '#94a3b8' }}>
          <div style={{ fontSize: 16, marginBottom: 16 }}>
            Loading predictions...
          </div>
          <div
            style={{ animation: 'pulse 2s infinite', display: 'inline-block' }}
          >
            ⏳
          </div>
        </div>
      ) : predictions ? (
        <div style={gridStyle}>
          {Object.entries(predictions).map(([index, data]) => (
            <IndexCard key={index} index={index} data={data} />
          ))}
        </div>
      ) : null}

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        @keyframes pulse {
          0%, 100% { opacity: 0.6; }
          50% { opacity: 1; }
        }
      `}</style>
    </div>
  );
}

function IndexCard({ index, data }) {
  const probability = data.overall_probability || 50;
  const color = data.recommendation_color || 'gray';
  const bgColor = getRecommendationBg(color);

  const getSignalIcon = (signal) => {
    if (signal.includes('✅')) return '✅';
    if (signal.includes('❌')) return '❌';
    if (signal.includes('⬆️')) return '⬆️';
    if (signal.includes('⬇️')) return '⬇️';
    if (signal.includes('📈')) return '📈';
    if (signal.includes('📉')) return '📉';
    if (signal.includes('📊')) return '📊';
    if (signal.includes('➡️')) return '➡️';
    if (signal.includes('⚠️')) return '⚠️';
    return '•';
  };

  return (
    <div style={cardStyle}>
      {/* Index Header */}
      <div style={indexHeaderStyle}>
        <div style={{ fontSize: 24, fontWeight: 700, color: '#3b82f6' }}>
          {index}
        </div>
        <div style={{ fontSize: 12, color: '#64748b' }}>
          {index === 'NIFTY'
            ? 'NIFTY 50 Index'
            : index === 'BANKNIFTY'
              ? 'Bank Nifty Index'
              : 'Sensex Index'}
        </div>
      </div>

      {/* Probability Meter */}
      <div style={probabilityStyle}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            marginBottom: 8
          }}
        >
          <span style={{ fontSize: 12, color: '#94a3b8' }}>
            Next Day Probability
          </span>
          <span style={{ fontSize: 14, fontWeight: 700, color: '#3b82f6' }}>
            {probability.toFixed(1)}%
          </span>
        </div>
        <div style={barStyle}>
          <div
            style={{
              width: `${probability}%`,
              height: '100%',
              background: `linear-gradient(to right, #10b981, #3b82f6)`,
              borderRadius: 4,
              transition: 'width 0.3s ease'
            }}
          />
        </div>
      </div>

      {/* Recommendation */}
      <div style={recommendationStyle(bgColor)}>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>
          Recommendation
        </div>
        <div style={{ fontSize: 13, color: '#e2e8f0' }}>
          {data.recommendation || 'NEUTRAL'}
        </div>
      </div>

      {/* Individual Scores */}
      <div style={scoresContainerStyle}>
        <ScoreItem
          label="Closing Strength"
          value={
            data.closing_strength
              ? `${data.closing_strength.toFixed(0)}%`
              : 'N/A'
          }
          score={data.closing_strength_score || 0}
        />
        <ScoreItem
          label="S/R Levels"
          value={data.support_resistance_score || 0}
          score={data.support_resistance_score || 0}
        />
        <ScoreItem
          label="Sector Sentiment"
          value={data.sector_sentiment || 0}
          score={data.sector_sentiment || 0}
        />
        <ScoreItem
          label="Volume Trend"
          value={data.volume_trend || 0}
          score={data.volume_trend || 0}
        />
        <ScoreItem
          label="PCR Ratio"
          value={data.pcr_value ? `${data.pcr_value}` : 'N/A'}
          score={data.pcr_score || 0}
        />
      </div>

      {/* Signals */}
      <div style={signalsStyle}>
        <div
          style={{
            fontSize: 12,
            fontWeight: 600,
            color: '#94a3b8',
            marginBottom: 10
          }}
        >
          📊 SIGNALS ({data.signals.length})
        </div>
        <div>
          {data.signals.map((signal, idx) => (
            <div key={idx} style={signalItemStyle}>
              <span style={{ marginRight: 8 }}>{getSignalIcon(signal)}</span>
              <span>{signal}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Info Footer */}
      <div style={footerStyle}>
        💡 Based on closing strength, support/resistance, sector sentiment,
        volume, and Put/Call Ratio (MVP accuracy ~60-70%)
      </div>
    </div>
  );
}

function ScoreItem({ label, value, score }) {
  const getColor = (s) => {
    if (s > 10) return '#10b981';
    if (s < -10) return '#ef4444';
    return '#94a3b8';
  };

  return (
    <div style={scoreItemStyle}>
      <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 4 }}>
        {label}
      </div>
      <div style={{ fontSize: 13, fontWeight: 600, color: getColor(score) }}>
        {typeof value === 'string' ? value : score > 0 ? `+${score}` : score}
      </div>
    </div>
  );
}

function getRecommendationBg(color) {
  switch (color) {
    case 'green':
      return '#065f46';
    case 'red':
      return '#7f1d1d';
    case 'yellow':
      return '#78350f';
    default:
      return '#1e293b';
  }
}

const containerStyle = {
  padding: '20px',
  color: '#e2e8f0'
};

const headerStyle = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  marginBottom: 24,
  paddingBottom: 16,
  borderBottom: '1px solid #334155'
};

const errorStyle = {
  background: '#7f1d1d',
  border: '1px solid #991b1b',
  padding: '12px 16px',
  borderRadius: 8,
  display: 'flex',
  alignItems: 'center',
  gap: 12,
  marginBottom: 20,
  color: '#fca5a5'
};

const gridStyle = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))',
  gap: 20
};

const cardStyle = {
  background: '#1e293b',
  border: '1px solid #334155',
  borderRadius: 12,
  padding: '20px',
  boxShadow: '0 1px 3px rgba(0,0,0,0.3)'
};

const indexHeaderStyle = {
  marginBottom: 16,
  paddingBottom: 12,
  borderBottom: '1px solid #334155'
};

const probabilityStyle = {
  marginBottom: 16,
  padding: '12px',
  background: '#0f172a',
  borderRadius: 8
};

const barStyle = {
  width: '100%',
  height: 8,
  background: '#334155',
  borderRadius: 4,
  overflow: 'hidden'
};

const recommendationStyle = (bgColor) => ({
  background: bgColor,
  padding: '12px',
  borderRadius: 8,
  marginBottom: 16,
  borderLeft: '3px solid #3b82f6'
});

const scoresContainerStyle = {
  display: 'grid',
  gridTemplateColumns: 'repeat(5, 1fr)',
  gap: 8,
  marginBottom: 16,
  padding: '12px',
  background: '#0f172a',
  borderRadius: 8
};

const scoreItemStyle = {
  padding: '8px',
  background: '#1e293b',
  borderRadius: 6,
  textAlign: 'center'
};

const signalsStyle = {
  marginBottom: 12,
  padding: '12px',
  background: '#0f172a',
  borderRadius: 8
};

const signalItemStyle = {
  padding: '6px 0',
  fontSize: 12,
  color: '#cbd5e1',
  display: 'flex',
  alignItems: 'center'
};

const footerStyle = {
  fontSize: 11,
  color: '#64748b',
  paddingTop: 12,
  borderTop: '1px solid #334155',
  marginTop: 12,
  textAlign: 'center'
};
