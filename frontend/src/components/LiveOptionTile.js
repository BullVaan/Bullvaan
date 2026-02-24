import { useState, useEffect } from 'react';

export default function LiveOptionTile({ symbol, signal }) {
  const [options, setOptions] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchOptions = async () => {
      try {
        setLoading(true);
        const res = await fetch(`http://127.0.0.1:8000/options?symbol=${symbol}`);
        const data = await res.json();
        
        if (data.error) {
          setError(data.error);
        } else {
          setOptions(data);
          setError('');
        }
      } catch (e) {
        setError('Cannot fetch options');
      } finally {
        setLoading(false);
      }
    };

    fetchOptions();
    // Refresh every 30 seconds
    const interval = setInterval(fetchOptions, 30000);
    return () => clearInterval(interval);
  }, [symbol]);

  if (loading) {
    return (
      <div style={containerStyle}>
        <div style={{ textAlign: 'center', color: '#64748b', padding: 20 }}>
          Loading options...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={containerStyle}>
        <div style={{ textAlign: 'center', color: '#ef4444', padding: 20 }}>
          {error}
        </div>
      </div>
    );
  }

  if (!options) return null;

  // Filter options based on signal
  const relevantOptions = options.options.filter(opt => {
    if (signal === 'BUY') return opt.type === 'CE';
    if (signal === 'SELL') return opt.type === 'PE';
    return true;
  });

  const atmOption = relevantOptions.find(o => o.label.startsWith('atm'));
  const otmOption = relevantOptions.find(o => o.label.startsWith('otm'));

  return (
    <div style={containerStyle}>
      {/* Header */}
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        marginBottom: 12,
        borderBottom: '1px solid #334155',
        paddingBottom: 10
      }}>
        <div>
          <div style={{ fontSize: 11, color: '#64748b' }}>LIVE OPTIONS</div>
          <div style={{ fontSize: 16, fontWeight: 700, color: '#22c55e' }}>
            {options.symbol} FEB
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 11, color: '#64748b' }}>Expiry</div>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#f59e0b' }}>
            26 Feb 2026
          </div>
        </div>
      </div>

      {/* Option Cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {atmOption && (
          <OptionRow 
            label="ATM" 
            strike={atmOption.strike} 
            type={atmOption.type}
            ltp={atmOption.ltp}
            color="#3b82f6"
          />
        )}
        {otmOption && (
          <OptionRow 
            label="OTM" 
            strike={otmOption.strike} 
            type={otmOption.type}
            ltp={otmOption.ltp}
            color="#a855f7"
          />
        )}
      </div>

      {/* Recommended */}
      {atmOption && (
        <div style={{ 
          marginTop: 12, 
          padding: '10px 14px',
          background: signal === 'BUY' ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)',
          border: `1px solid ${signal === 'BUY' ? '#22c55e' : '#ef4444'}`,
          borderRadius: 8,
          textAlign: 'center'
        }}>
          <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>
            RECOMMENDED
          </div>
          <div style={{ fontSize: 16, fontWeight: 700 }}>
            {signal === 'BUY' ? 'BUY' : 'BUY'} {atmOption.strike} {atmOption.type}
          </div>
          <div style={{ 
            fontSize: 20, 
            fontWeight: 700, 
            color: signal === 'BUY' ? '#22c55e' : '#ef4444',
            marginTop: 4
          }}>
            ₹{atmOption.ltp?.toFixed(2) || '—'}
          </div>
        </div>
      )}

      {/* Refresh indicator */}
      <div style={{ 
        marginTop: 10, 
        fontSize: 10, 
        color: '#475569', 
        textAlign: 'center' 
      }}>
        Auto-refresh: 30s
      </div>
    </div>
  );
}

function OptionRow({ label, strike, type, ltp, color }) {
  return (
    <div style={{
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: '10px 12px',
      background: '#0f172a',
      borderRadius: 8,
      border: `1px solid ${color}`
    }}>
      <div>
        <span style={{ 
          fontSize: 10, 
          color, 
          fontWeight: 600,
          marginRight: 8 
        }}>
          {label}
        </span>
        <span style={{ fontSize: 15, fontWeight: 700 }}>
          {strike} {type}
        </span>
      </div>
      <div style={{ 
        fontSize: 18, 
        fontWeight: 700, 
        color: '#f59e0b' 
      }}>
        ₹{ltp?.toFixed(2) || '—'}
      </div>
    </div>
  );
}

const containerStyle = {
  background: '#020617',
  border: '2px solid #334155',
  borderRadius: 10,
  padding: 18,
  marginBottom: 18,
  width: 280,
  minHeight: 200
};
