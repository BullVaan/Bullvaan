import { useState, useEffect } from 'react';

export default function RoleCard({ role, indicators }) {
  const roleColors = {
    Trend: { bg: '#1e3a5f', border: '#3b82f6', label: '📈' },
    Momentum: { bg: '#3a1e4e', border: '#a855f7', label: '⚡' },
    Strength: { bg: '#1e3a2e', border: '#10b981', label: '💪' }
  };

  const colors = {
    BUY: '#16a34a',
    SELL: '#dc2626',
    NEUTRAL: '#eab308'
  };

  const style = roleColors[role] || {
    bg: '#020617',
    border: '#334155',
    label: '•'
  };

  // Calculate role consensus from indicators
  const getConsensus = () => {
    if (!indicators || indicators.length === 0) return 'NEUTRAL';
    const votes = indicators.map((ind) => ind.signal);
    const buyCount = votes.filter((v) => v === 'BUY').length;
    const sellCount = votes.filter((v) => v === 'SELL').length;

    if (buyCount > sellCount) return 'BUY';
    if (sellCount > buyCount) return 'SELL';
    return 'NEUTRAL';
  };

  const consensus = getConsensus();

  return (
    <div
      style={{
        flex: 1,
        padding: 16,
        borderRadius: 12,
        background: style.bg,
        border: `2px solid ${style.border}`,
        boxShadow: `0 0 15px rgba(59, 130, 246, 0.2)`,
        transition: '0.3s'
      }}
    >
      {/* Role Header */}
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 15 }}>
        <span style={{ fontSize: 20, marginRight: 8 }}>{style.label}</span>
        <div>
          <div style={{ fontSize: 14, color: '#94a3b8' }}>Role</div>
          <div
            style={{ fontSize: 16, fontWeight: 'bold', color: style.border }}
          >
            {role}
          </div>
        </div>
      </div>

      {/* Indicators List */}
      <div style={{ marginBottom: 12 }}>
        {indicators &&
          indicators.map((indicator, idx) => (
            <div
              key={idx}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '8px 10px',
                marginBottom: 6,
                background: '#0f172a',
                borderRadius: 8,
                border: `1px solid ${colors[indicator.signal]}`,
                fontSize: 13
              }}
            >
              <span style={{ color: '#cbd5e1' }}>{indicator.name}</span>
              <span
                style={{
                  fontWeight: 'bold',
                  color: colors[indicator.signal],
                  minWidth: 50,
                  textAlign: 'right'
                }}
              >
                {indicator.signal}
              </span>
            </div>
          ))}
      </div>

      {/* Role Consensus */}
      <div
        style={{
          padding: 10,
          borderRadius: 8,
          background: colors[consensus],
          textAlign: 'center',
          color: 'black',
          fontWeight: 'bold',
          fontSize: 14
        }}
      >
        {consensus}
      </div>
    </div>
  );
}
