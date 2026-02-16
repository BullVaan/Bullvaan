import { useEffect, useState } from 'react';

export default function SignalCard({ name, signal }) {
  const [flash, setFlash] = useState(false);
  const [prevSignal, setPrevSignal] = useState(signal);

  useEffect(() => {
    if (prevSignal !== signal) {
      setFlash(true);
      setTimeout(() => setFlash(false), 600);
      setPrevSignal(signal);
    }
  }, [signal, prevSignal]);

  const colors = {
    BUY: '#16a34a',
    SELL: '#dc2626',
    NEUTRAL: '#eab308'
  };

  return (
    <div
      style={{
        width: 150,
        padding: 16,
        borderRadius: 12,
        background: flash ? colors[signal] : '#020617',
        border: `1px solid ${colors[signal]}`,
        textAlign: 'center',
        transition: '0.4s',
        boxShadow: flash
          ? `0 0 20px ${colors[signal]}`
          : '0 0 10px rgba(0,0,0,0.3)'
      }}
    >
      <div style={{ fontSize: 14, marginBottom: 10 }}>{name}</div>

      <div
        style={{
          fontSize: 20,
          fontWeight: 'bold',
          color: colors[signal]
        }}
      >
        {signal}
      </div>
    </div>
  );
}
