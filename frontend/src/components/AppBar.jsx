import React from 'react';
import MarketStatus from './MarketStatus';

export default function AppBar({ onLogout }) {
  return (
    <header
      style={{
        width: '100%',
        background: '#0f172a',
        borderBottom: '1px solid #334155',
        padding: '0 24px',
        height: 60,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        position: 'sticky',
        top: 0,
        zIndex: 1100,
        boxShadow: '0 2px 16px 0 rgba(20,30,60,0.10)'
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 32,
          justifyContent: 'center',
          width: '100%'
        }}
      >
        <span
          style={{
            fontWeight: 'bold',
            fontSize: 22,
            color: '#38bdf8',
            letterSpacing: 1,
            textShadow: '0 2px 8px rgba(0,0,0,0.10)'
          }}
        >
          Bullvaan
        </span>
        <MarketStatus />
        <button
          onClick={onLogout}
          style={{
            padding: '8px 18px',
            background: 'linear-gradient(90deg,#ef4444 60%,#fbbf24 100%)',
            border: 'none',
            color: 'white',
            cursor: 'pointer',
            borderRadius: 8,
            fontWeight: 'bold',
            marginLeft: 8,
            boxShadow: '0 2px 8px #ef444422',
            fontSize: 16,
            letterSpacing: 1
          }}
        >
          Logout
        </button>
      </div>
    </header>
  );
}
