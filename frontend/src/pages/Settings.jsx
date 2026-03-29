import { useState, useEffect } from 'react';
import { Save } from 'lucide-react';
import { getAuthHeaders } from '../utils/auth';

function nameFromEmail(email) {
  if (!email) return '';
  const local = email.split('@')[0];
  return local.replace(/[._-]/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function Settings() {
  const [activeTab, setActiveTab] = useState('account');

  const email = localStorage.getItem('email') || '';
  const fullName = nameFromEmail(email);
  const [mobile, setMobile] = useState('');
  const [profileMsg, setProfileMsg] = useState('');
  const [profileLoading, setProfileLoading] = useState(false);

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const res = await fetch('/api/user/profile', { headers: getAuthHeaders() });
        if (res.ok) {
          const data = await res.json();
          if (data.mobile) setMobile(data.mobile);
        }
      } catch (_) {}
    };
    fetchProfile();
  }, []);

  const saveProfile = async () => {
    setProfileLoading(true);
    setProfileMsg('');
    try {
      const res = await fetch('/api/user/profile', {
        method: 'PATCH',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ full_name: fullName, mobile })
      });
      const data = await res.json();
      if (res.ok) {
        setProfileMsg('Saved!');
      } else {
        setProfileMsg(data.detail || 'Error saving profile');
      }
    } catch (err) {
      setProfileMsg(err.message);
    } finally {
      setProfileLoading(false);
      setTimeout(() => setProfileMsg(''), 3000);
    }
  };

  const [kiteCredentials, setKiteCredentials] = useState({ apiKey: '', accessToken: '', hasCredentials: false });
  const [credentialsMessage, setCredentialsMessage] = useState('');
  const [credentialsLoading, setCredentialsLoading] = useState(false);

  useEffect(() => { checkKiteCredentialsStatus(); }, []);

  const checkKiteCredentialsStatus = async () => {
    try {
      const res = await fetch('/user/kite-credentials/status', { headers: getAuthHeaders() });
      const data = await res.json();
      setKiteCredentials((prev) => ({ ...prev, hasCredentials: data.has_credentials }));
    } catch (err) { console.error('Error checking credentials:', err); }
  };

  const handleSaveKiteCredentials = async (e) => {
    e.preventDefault();
    setCredentialsLoading(true);
    setCredentialsMessage('');
    if (!kiteCredentials.apiKey || !kiteCredentials.accessToken) {
      setCredentialsMessage('API Key and Access Token are required');
      setCredentialsLoading(false);
      return;
    }
    try {
      const res = await fetch('/user/kite-credentials/save', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ api_key: kiteCredentials.apiKey, access_token: kiteCredentials.accessToken })
      });
      const data = await res.json();
      if (data.status === 'ok') {
        setCredentialsMessage('Credentials saved and encrypted successfully!');
        setKiteCredentials({ apiKey: '', accessToken: '', hasCredentials: true });
        checkKiteCredentialsStatus();
        setTimeout(() => setCredentialsMessage(''), 3000);
      } else {
        setCredentialsMessage(data.detail || 'Error saving credentials');
      }
    } catch (err) { setCredentialsMessage('Error: ' + err.message); }
    finally { setCredentialsLoading(false); }
  };

  const handleDeleteKiteCredentials = async () => {
    if (!window.confirm('Delete saved credentials? You will need to add new ones to trade.')) return;
    setCredentialsLoading(true);
    setCredentialsMessage('');
    try {
      const res = await fetch('/user/kite-credentials', { method: 'DELETE', headers: getAuthHeaders() });
      const data = await res.json();
      if (data.status === 'ok') {
        setCredentialsMessage('Credentials deleted successfully');
        setKiteCredentials({ apiKey: '', accessToken: '', hasCredentials: false });
        setTimeout(() => setCredentialsMessage(''), 3000);
      } else {
        setCredentialsMessage(data.detail || 'Error deleting credentials');
      }
    } catch (err) { setCredentialsMessage('Error: ' + err.message); }
    finally { setCredentialsLoading(false); }
  };

  const tabs = [
    { id: 'account', label: 'Account' },
    { id: 'api', label: 'API' }
  ];

  return (
    <div style={containerStyle}>
      <div style={headerStyle}>
        <h1 style={{ fontSize: 28, fontWeight: 700, margin: 0 }}>Settings</h1>
      </div>

      <div style={tabsContainerStyle}>
        {tabs.map((tab) => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)}
            style={{ ...tabButtonStyle, background: activeTab === tab.id ? '#22c55e' : '#1e293b', color: activeTab === tab.id ? 'black' : '#94a3b8', borderBottom: activeTab === tab.id ? '3px solid #22c55e' : 'none' }}>
            {tab.label}
          </button>
        ))}
      </div>

      <div style={contentStyle}>
        {activeTab === 'account' && (
          <Section title="Account">
            <SettingItem>
              <Label>Full Name</Label>
              <Input type="text" value={fullName} readOnly style={{ opacity: 0.6, cursor: 'default' }} />
              <small style={{ color: '#475569', marginTop: 4, display: 'block' }}>Derived from your email address</small>
            </SettingItem>
            <SettingItem>
              <Label>Email Address</Label>
              <Input type="email" value={email} readOnly style={{ opacity: 0.6, cursor: 'default' }} />
            </SettingItem>
            <SettingItem>
              <Label>Mobile Number</Label>
              <Input type="tel" value={mobile} onChange={(e) => setMobile(e.target.value)} placeholder="+91 9876543210" />
            </SettingItem>
            {profileMsg && (
              <div style={{ padding: '10px 14px', borderRadius: 8, marginBottom: 16, fontSize: 13, background: profileMsg === 'Saved!' ? '#065f46' : '#7f1d1d', color: profileMsg === 'Saved!' ? '#86efac' : '#fca5a5' }}>
                {profileMsg === 'Saved!' ? 'Profile saved successfully!' : profileMsg}
              </div>
            )}
            <button onClick={saveProfile} disabled={profileLoading}
              style={{ padding: '10px 24px', borderRadius: 8, border: 'none', background: '#22c55e', color: 'black', cursor: profileLoading ? 'not-allowed' : 'pointer', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8, opacity: profileLoading ? 0.6 : 1 }}>
              <Save size={16} />
              {profileLoading ? 'Saving...' : 'Save Profile'}
            </button>
          </Section>
        )}

        {activeTab === 'api' && (
          <Section title="Kite API Credentials">
            <InfoBox>Save your Zerodha Kite API credentials securely. Your credentials are encrypted and used for trading orders only.</InfoBox>
            <div style={{ padding: 16, borderRadius: 8, marginBottom: 16, background: kiteCredentials.hasCredentials ? '#065f46' : '#7f1d1d', border: `1px solid ${kiteCredentials.hasCredentials ? '#10b981' : '#dc2626'}`, color: kiteCredentials.hasCredentials ? '#86efac' : '#fca5a5' }}>
              <p style={{ margin: 0, fontWeight: 600 }}>{kiteCredentials.hasCredentials ? 'Credentials Saved' : 'No Credentials Saved'}</p>
              <small style={{ display: 'block', marginTop: 4 }}>{kiteCredentials.hasCredentials ? 'Your Kite credentials are securely stored.' : "Without credentials, trading orders will use the application's shared account."}</small>
            </div>
            {credentialsMessage && (
              <div style={{ padding: 12, borderRadius: 8, marginBottom: 16, fontSize: 13, background: credentialsMessage.includes('successfully') || credentialsMessage.includes('deleted') ? '#065f46' : '#7f1d1d', color: credentialsMessage.includes('successfully') || credentialsMessage.includes('deleted') ? '#86efac' : '#fca5a5' }}>
                {credentialsMessage}
              </div>
            )}
            <form onSubmit={handleSaveKiteCredentials} style={{ marginBottom: 24 }}>
              <SettingItem>
                <Label>API Key</Label>
                <Input type="password" value={kiteCredentials.apiKey} onChange={(e) => setKiteCredentials((prev) => ({ ...prev, apiKey: e.target.value }))} placeholder="Your Zerodha API key" disabled={credentialsLoading} />
                <small style={{ color: '#64748b', marginTop: 4, display: 'block' }}>Get this from Kite Console &rarr; Settings &rarr; API Consents</small>
              </SettingItem>
              <SettingItem>
                <Label>24-Hour Access Token</Label>
                <Input type="password" value={kiteCredentials.accessToken} onChange={(e) => setKiteCredentials((prev) => ({ ...prev, accessToken: e.target.value }))} placeholder="Your 24-hour access token" disabled={credentialsLoading} />
                <small style={{ color: '#64748b', marginTop: 4, display: 'block' }}>Generate this in Kite Console after login. Token expires after 24 hours.</small>
              </SettingItem>
              <button type="submit" disabled={credentialsLoading}
                style={{ padding: '10px 20px', borderRadius: 6, border: 'none', background: '#22c55e', color: 'black', cursor: credentialsLoading ? 'not-allowed' : 'pointer', fontWeight: 600, opacity: credentialsLoading ? 0.6 : 1 }}>
                {credentialsLoading ? 'Saving...' : 'Save Credentials'}
              </button>
            </form>
            <SubSection title="How to Get Credentials">
              <ol style={{ color: '#cbd5e1', fontSize: 13, lineHeight: 1.8 }}>
                <li>Login to <a href="https://kite.trade" target="_blank" rel="noopener noreferrer" style={{ color: '#22c55e', textDecoration: 'none' }}>Kite Console</a></li>
                <li>Go to <strong>Settings</strong> &rarr; <strong>API Consents</strong></li>
                <li>Copy your <strong>API Key</strong></li>
                <li>Click <strong>Generate Token</strong> to get a new 24-hour access token</li>
                <li>Copy the access token (keep it secret!)</li>
                <li>Paste both above and click "Save Credentials"</li>
              </ol>
            </SubSection>
            {kiteCredentials.hasCredentials && (
              <DangerZone>
                <button onClick={handleDeleteKiteCredentials} disabled={credentialsLoading}
                  style={{ ...dangerButtonStyle, opacity: credentialsLoading ? 0.6 : 1, cursor: credentialsLoading ? 'not-allowed' : 'pointer' }}>
                  {credentialsLoading ? 'Deleting...' : 'Delete Credentials'}
                </button>
                <small style={{ color: '#64748b', marginTop: 8, display: 'block' }}>Removes your saved credentials. You can add new ones anytime.</small>
              </DangerZone>
            )}
            {!kiteCredentials.hasCredentials && (
              <InfoBox>When you provide credentials, all your trading orders will execute under your own Kite account in real-time.</InfoBox>
            )}
          </Section>
        )}
      </div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div style={sectionStyle}>
      <h2 style={{ fontSize: 20, fontWeight: 600, marginBottom: 20, borderBottom: '1px solid #334155', paddingBottom: 12 }}>{title}</h2>
      {children}
    </div>
  );
}

function SubSection({ title, children }) {
  return (
    <div style={{ border: '1px solid #334155', borderRadius: 8, padding: 16, marginBottom: 16 }}>
      <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: '#cbd5e1' }}>{title}</h3>
      {children}
    </div>
  );
}

function SettingItem({ children }) { return <div style={{ marginBottom: 16 }}>{children}</div>; }

function Label({ children }) {
  return <label style={{ display: 'block', fontSize: 14, fontWeight: 600, marginBottom: 8, color: '#cbd5e1' }}>{children}</label>;
}

function Input({ ...props }) {
  return <input {...props} style={{ width: '100%', padding: '10px 12px', borderRadius: 6, border: '1px solid #334155', background: '#1e293b', color: '#e2e8f0', fontSize: 14, outline: 'none', ...(props.style || {}) }} />;
}

function InfoBox({ children }) {
  return <div style={{ background: '#065f46', border: '1px solid #10b981', padding: 12, borderRadius: 8, marginBottom: 16, color: '#86efac', fontSize: 13 }}>{children}</div>;
}

function DangerZone({ children }) {
  return <div style={{ marginTop: 24, paddingTop: 16, borderTop: '1px solid #334155' }}>{children}</div>;
}

const dangerButtonStyle = { padding: '10px 16px', borderRadius: 6, border: '1px solid #ef4444', background: 'transparent', color: '#ef4444', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8, transition: '0.2s' };
const containerStyle = { padding: '20px', color: '#e2e8f0' };
const headerStyle = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24, paddingBottom: 16, borderBottom: '1px solid #334155' };
const tabsContainerStyle = { display: 'flex', gap: 8, marginBottom: 24, borderBottom: '1px solid #334155' };
const tabButtonStyle = { padding: '12px 16px', border: 'none', borderRadius: '8px 8px 0 0', cursor: 'pointer', fontWeight: 600, transition: '0.2s', whiteSpace: 'nowrap' };
const contentStyle = { background: '#0f172a', borderRadius: 12, padding: '24px' };
const sectionStyle = { marginBottom: 24 };