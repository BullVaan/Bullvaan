import { useState } from 'react';

const fieldStyle = {
  width: '100%',
  background: '#0f172a',
  border: '1px solid #1e293b',
  borderRadius: 8,
  padding: '10px 14px',
  fontSize: 13,
  color: '#e2e8f0',
  outline: 'none',
  fontFamily: 'inherit'
};

const labelStyle = {
  display: 'block',
  fontSize: 12,
  color: '#64748b',
  marginBottom: 6,
  fontWeight: 600,
  textTransform: 'uppercase',
  letterSpacing: '0.5px'
};

export default function ContactUs() {
  const [form, setForm] = useState({ name: '', email: '', message: '' });

  const handleChange = (key) => (e) =>
    setForm({ ...form, [key]: e.target.value });

  return (
    <div style={{ padding: '60px', maxWidth: 640, margin: '0 auto' }}>
      <h1
        style={{
          fontSize: 38,
          fontWeight: 800,
          marginBottom: 8,
          background: 'linear-gradient(90deg, #38bdf8, #fff)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent'
        }}
      >
        Contact Us
      </h1>
      <p style={{ fontSize: 14, color: '#475569', marginBottom: 28 }}>
        Have a question or feedback? We'd love to hear from you. Fill out the
        form and we'll get back to you within 24 hours.
      </p>

      <div style={{ marginBottom: 18 }}>
        <label style={labelStyle}>Your Name</label>
        <input
          type="text"
          placeholder="Pankaj"
          value={form.name}
          onChange={handleChange('name')}
          style={fieldStyle}
        />
      </div>

      <div style={{ marginBottom: 18 }}>
        <label style={labelStyle}>Email Address</label>
        <input
          type="email"
          placeholder="you@example.com"
          value={form.email}
          onChange={handleChange('email')}
          style={fieldStyle}
        />
      </div>

      <div style={{ marginBottom: 24 }}>
        <label style={labelStyle}>Message</label>
        <textarea
          placeholder="Tell us what's on your mind..."
          value={form.message}
          onChange={handleChange('message')}
          style={{ ...fieldStyle, height: 120, resize: 'vertical' }}
        />
      </div>

      <button
        style={{
          width: '100%',
          padding: 12,
          borderRadius: 8,
          border: 'none',
          background: 'linear-gradient(135deg, #2563eb, #38bdf8)',
          color: '#fff',
          fontSize: 14,
          fontWeight: 700,
          cursor: 'pointer'
        }}
      >
        Send Message →
      </button>
    </div>
  );
}
