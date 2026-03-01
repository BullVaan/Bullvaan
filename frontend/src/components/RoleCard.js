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
    const neutralCount = votes.filter((v) => v === 'NEUTRAL').length;
    const total = votes.length;

    // If BUY and SELL both present → conflict → NEUTRAL
    if (buyCount > 0 && sellCount > 0) return 'NEUTRAL';
    // For 3+ indicators: if NEUTRAL is majority (2+ out of 3) → NEUTRAL
    if (total >= 3 && neutralCount >= 2) return 'NEUTRAL';
    // Otherwise the active direction wins
    if (buyCount > 0) return 'BUY';
    if (sellCount > 0) return 'SELL';
    return 'NEUTRAL';
  };

  const consensus = getConsensus();

  // Get background color based on consensus - solid colors with transparency
  const getBackgroundColor = () => {
    switch(consensus) {
      case 'BUY':
        return 'rgba(22, 163, 74, 0.15)';
      case 'SELL':
        return 'rgba(220, 38, 38, 0.15)';
      case 'NEUTRAL':
        return 'rgba(234, 179, 8, 0.15)';
      default:
        return style.bg;
    }
  };

  // Get border color based on consensus
  const getBorderColor = () => {
    switch(consensus) {
      case 'BUY':
        return '#16a34a';
      case 'SELL':
        return '#dc2626';
      case 'NEUTRAL':
        return '#eab308';
      default:
        return style.border;
    }
  };

  return (
    <div
      style={{
        flex: 1,
        padding: 16,
        borderRadius: 12,
        background: getBackgroundColor(),
        border: `2px solid ${getBorderColor()}`,
        boxShadow: `0 0 20px ${colors[consensus]}40`,
        transition: '0.4s'
      }}
    >
      {/* Role Header */}
      <div style={{ textAlign: 'center', marginBottom: 15 }}>
        <div
          style={{ fontSize: 18, fontWeight: 'bold', color: '#cbd5e1' }}
        >
          {role}
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
