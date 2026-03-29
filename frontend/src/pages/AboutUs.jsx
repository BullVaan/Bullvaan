export default function AboutUs() {
  const team = [
    { avatar: '👨‍💼', name: 'Pankaj Sharma', role: 'Founder & Developer' },
    { avatar: '👨‍💻', name: 'Ashish Yadav', role: 'Founder & Developer' },
    { avatar: '⚡', name: 'Zero Latency', role: 'Hosted on Render + Netlify' }
  ];

  return (
    <div style={{ padding: '60px', maxWidth: 800, margin: '0 auto' }}>
      <h1
        style={{
          fontSize: 38,
          fontWeight: 800,
          marginBottom: 16,
          background: 'linear-gradient(90deg, #38bdf8, #fff)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent'
        }}
      >
        About BullVaan
      </h1>
      <p
        style={{
          fontSize: 15,
          color: '#64748b',
          lineHeight: 1.8,
          marginBottom: 20
        }}
      >
        BullVaan is a modern algorithmic trading platform built for Indian
        retail traders. We combine real-time market data, proven technical
        strategies, and automated execution — so you can trade faster and
        smarter.
      </p>
      <p
        style={{
          fontSize: 15,
          color: '#64748b',
          lineHeight: 1.8,
          marginBottom: 32
        }}
      >
        Our platform connects directly to Zerodha via KiteConnect, giving you
        institutional-grade tools without the institutional price tag. Whether
        you're scalping intraday or building swing positions, BullVaan has a
        strategy for you.
      </p>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: 16
        }}
      >
        {team.map(({ avatar, name, role }) => (
          <div
            key={name}
            style={{
              background: '#0f172a',
              border: '1px solid #1e293b',
              borderRadius: 12,
              padding: 20,
              textAlign: 'center'
            }}
          >
            <div style={{ fontSize: 40, marginBottom: 8 }}>{avatar}</div>
            <div style={{ fontSize: 15, fontWeight: 700, color: '#e2e8f0' }}>
              {name}
            </div>
            <div style={{ fontSize: 12, color: '#475569', marginTop: 4 }}>
              {role}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
