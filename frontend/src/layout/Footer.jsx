export default function Footer() {
  return (
    <div
      style={{
        background: '#0a0f1e',
        borderTop: '1px solid #1e293b',
        padding: '14px 28px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexShrink: 0
      }}
    >
      <div style={{ fontSize: 12, color: '#475569' }}>
        © 2026{' '}
        <span style={{ color: '#38bdf8', fontWeight: 600 }}>BullVaan</span>. All
        rights reserved.
      </div>
      <div style={{ display: 'flex', gap: 20 }}>
        {['Privacy Policy', 'Terms of Service', 'Support'].map((link) => (
          <button
            key={link}
            type="button"
            style={{
              fontSize: 12,
              color: '#475569',
              textDecoration: 'none',
              cursor: 'pointer',
              background: 'none',
              border: 'none',
              padding: 0
            }}
          >
            {link}
          </button>
        ))}
      </div>
    </div>
  );
}
