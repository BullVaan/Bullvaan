import { useState, useEffect } from 'react';
import { Save, LogOut, Bell, Lock, Sliders, Palette, Key } from 'lucide-react';
import { getAuthHeaders } from '../utils/auth';

export default function Settings() {
  const [activeTab, setActiveTab] = useState('account');
  const [saved, setSaved] = useState(false);

  // Kite Credentials State
  const [kiteCredentials, setKiteCredentials] = useState({
    apiKey: '',
    accessToken: '',
    hasCredentials: false
  });
  const [credentialsMessage, setCredentialsMessage] = useState('');
  const [credentialsLoading, setCredentialsLoading] = useState(false);

  // Load Kite credentials status on component mount
  useEffect(() => {
    checkKiteCredentialsStatus();
  }, []);

  // Account Settings State
  const [account, setAccount] = useState({
    name: localStorage.getItem('user_name') || 'Trader',
    email: localStorage.getItem('user_email') || 'trader@example.com',
    phone: localStorage.getItem('user_phone') || '+91 9876543210'
  });

  // Trading Preferences State
  const [trading, setTrading] = useState({
    defaultPositionSize: localStorage.getItem('position_size') || '1',
    maxRiskPercent: localStorage.getItem('max_risk') || '2',
    defaultStopLoss: localStorage.getItem('default_sl') || '2',
    defaultTakeProfit: localStorage.getItem('default_tp') || '5',
    allocationNifty: localStorage.getItem('alloc_nifty') || '40',
    allocationBankNifty: localStorage.getItem('alloc_banknifty') || '30',
    allocationStocks: localStorage.getItem('alloc_stocks') || '30'
  });

  // Notifications State
  const [notifications, setNotifications] = useState({
    emailAlerts: localStorage.getItem('email_alerts') === 'true',
    smsAlerts: localStorage.getItem('sms_alerts') === 'true',
    overnightAlert: localStorage.getItem('overnight_alert') === 'true',
    priceAlert: localStorage.getItem('price_alert') === 'true',
    alertThreshold: localStorage.getItem('alert_threshold') || '5'
  });

  // Display Settings State
  const [display, setDisplay] = useState({
    theme: localStorage.getItem('theme') || 'dark',
    chartType: localStorage.getItem('chart_type') || 'candlestick',
    defaultTimeframe: localStorage.getItem('default_tf') || '5m',
    decimalPlaces: localStorage.getItem('decimal_places') || '2'
  });

  // API Settings State
  const [api, setApi] = useState({
    apiKey: localStorage.getItem('api_key')
      ? '••••••••' + localStorage.getItem('api_key')?.slice(-4)
      : 'Not configured',
    apiSecret: localStorage.getItem('api_secret')
      ? '••••••••'
      : 'Not configured',
    syncFrequency: localStorage.getItem('sync_frequency') || '10'
  });

  const handleAccountChange = (field, value) => {
    setAccount((prev) => ({ ...prev, [field]: value }));
  };

  const handleTradingChange = (field, value) => {
    setTrading((prev) => ({ ...prev, [field]: value }));
  };

  const handleNotificationChange = (field, value) => {
    setNotifications((prev) => ({ ...prev, [field]: value }));
  };

  const handleDisplayChange = (field, value) => {
    setDisplay((prev) => ({ ...prev, [field]: value }));
  };

  const saveSettings = () => {
    // Save Account
    localStorage.setItem('user_name', account.name);
    localStorage.setItem('user_email', account.email);
    localStorage.setItem('user_phone', account.phone);

    // Save Trading
    localStorage.setItem('position_size', trading.defaultPositionSize);
    localStorage.setItem('max_risk', trading.maxRiskPercent);
    localStorage.setItem('default_sl', trading.defaultStopLoss);
    localStorage.setItem('default_tp', trading.defaultTakeProfit);
    localStorage.setItem('alloc_nifty', trading.allocationNifty);
    localStorage.setItem('alloc_banknifty', trading.allocationBankNifty);
    localStorage.setItem('alloc_stocks', trading.allocationStocks);

    // Save Notifications
    localStorage.setItem('email_alerts', notifications.emailAlerts);
    localStorage.setItem('sms_alerts', notifications.smsAlerts);
    localStorage.setItem('overnight_alert', notifications.overnightAlert);
    localStorage.setItem('price_alert', notifications.priceAlert);
    localStorage.setItem('alert_threshold', notifications.alertThreshold);

    // Save Display
    localStorage.setItem('theme', display.theme);
    localStorage.setItem('chart_type', display.chartType);
    localStorage.setItem('default_tf', display.defaultTimeframe);
    localStorage.setItem('decimal_places', display.decimalPlaces);

    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  // Kite Credentials Functions
  const checkKiteCredentialsStatus = async () => {
    try {
      const res = await fetch('/user/kite-credentials/status', {
        headers: getAuthHeaders()
      });
      const data = await res.json();
      setKiteCredentials((prev) => ({
        ...prev,
        hasCredentials: data.has_credentials
      }));
    } catch (err) {
      console.error('Error checking credentials:', err);
    }
  };

  const handleSaveKiteCredentials = async (e) => {
    e.preventDefault();
    setCredentialsLoading(true);
    setCredentialsMessage('');

    if (!kiteCredentials.apiKey || !kiteCredentials.accessToken) {
      setCredentialsMessage('❌ API Key and Access Token are required');
      setCredentialsLoading(false);
      return;
    }

    try {
      const res = await fetch('/user/kite-credentials/save', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          api_key: kiteCredentials.apiKey,
          access_token: kiteCredentials.accessToken
        })
      });

      const data = await res.json();

      if (data.status === 'ok') {
        setCredentialsMessage(
          '✅ Credentials saved and encrypted successfully!'
        );
        setKiteCredentials({
          apiKey: '',
          accessToken: '',
          hasCredentials: true
        });
        checkKiteCredentialsStatus();
        setTimeout(() => setCredentialsMessage(''), 3000);
      } else {
        setCredentialsMessage(
          `❌ ${data.detail || 'Error saving credentials'}`
        );
      }
    } catch (err) {
      setCredentialsMessage(`❌ Error: ${err.message}`);
    } finally {
      setCredentialsLoading(false);
    }
  };

  const handleDeleteKiteCredentials = async () => {
    if (
      !window.confirm(
        'Delete saved credentials? You will need to add new ones to trade.'
      )
    ) {
      return;
    }

    setCredentialsLoading(true);
    setCredentialsMessage('');

    try {
      const res = await fetch('/user/kite-credentials', {
        method: 'DELETE',
        headers: getAuthHeaders()
      });

      const data = await res.json();

      if (data.status === 'ok') {
        setCredentialsMessage('✅ Credentials deleted successfully');
        setKiteCredentials({
          apiKey: '',
          accessToken: '',
          hasCredentials: false
        });
        setTimeout(() => setCredentialsMessage(''), 3000);
      } else {
        setCredentialsMessage(
          `❌ ${data.detail || 'Error deleting credentials'}`
        );
      }
    } catch (err) {
      setCredentialsMessage(`❌ Error: ${err.message}`);
    } finally {
      setCredentialsLoading(false);
    }
  };

  return (
    <div style={containerStyle}>
      <div style={headerStyle}>
        <h1 style={{ fontSize: 28, fontWeight: 700, margin: 0 }}>
          ⚙️ Settings
        </h1>
        <button
          onClick={saveSettings}
          style={{
            padding: '10px 20px',
            borderRadius: 8,
            border: 'none',
            background: '#22c55e',
            color: 'black',
            cursor: 'pointer',
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            gap: 8
          }}
        >
          <Save size={18} />
          {saved ? '✅ Saved!' : 'Save Changes'}
        </button>
      </div>

      {/* Tabs */}
      <div style={tabsContainerStyle}>
        {[
          { id: 'account', label: '👤 Account', icon: '👤' },
          { id: 'trading', label: '📊 Trading', icon: '📊' },
          { id: 'notifications', label: '🔔 Notifications', icon: '🔔' },
          { id: 'display', label: '🎨 Display', icon: '🎨' },
          { id: 'api', label: '🔑 API', icon: '🔑' }
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              ...tabButtonStyle,
              background: activeTab === tab.id ? '#22c55e' : '#1e293b',
              color: activeTab === tab.id ? 'black' : '#94a3b8',
              borderBottom: activeTab === tab.id ? '3px solid #22c55e' : 'none'
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={contentStyle}>
        {/* ACCOUNT SETTINGS */}
        {activeTab === 'account' && (
          <Section title="Account Settings">
            <SettingItem>
              <Label>Full Name</Label>
              <Input
                type="text"
                value={account.name}
                onChange={(e) => handleAccountChange('name', e.target.value)}
                placeholder="Your name"
              />
            </SettingItem>

            <SettingItem>
              <Label>Email Address</Label>
              <Input
                type="email"
                value={account.email}
                onChange={(e) => handleAccountChange('email', e.target.value)}
                placeholder="your@email.com"
              />
            </SettingItem>

            <SettingItem>
              <Label>Phone Number</Label>
              <Input
                type="tel"
                value={account.phone}
                onChange={(e) => handleAccountChange('phone', e.target.value)}
                placeholder="+91 9876543210"
              />
            </SettingItem>

            <SettingItem>
              <Label>Change Password</Label>
              <Input type="password" placeholder="Enter new password" />
              <Input
                type="password"
                placeholder="Confirm password"
                style={{ marginTop: 8 }}
              />
            </SettingItem>

            <DangerZone>
              <button
                onClick={() => {
                  localStorage.removeItem('auth');
                  window.location.href = '/';
                }}
                style={logoutButtonStyle}
              >
                <LogOut size={18} />
                Logout
              </button>
            </DangerZone>
          </Section>
        )}

        {/* TRADING PREFERENCES */}
        {activeTab === 'trading' && (
          <Section title="Trading Preferences">
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: 16,
                marginBottom: 24
              }}
            >
              <SettingItem>
                <Label>Default Position Size (Lots)</Label>
                <Input
                  type="number"
                  value={trading.defaultPositionSize}
                  onChange={(e) =>
                    handleTradingChange('defaultPositionSize', e.target.value)
                  }
                  min="0.5"
                  step="0.5"
                />
              </SettingItem>

              <SettingItem>
                <Label>Max Risk per Trade (%)</Label>
                <Input
                  type="number"
                  value={trading.maxRiskPercent}
                  onChange={(e) =>
                    handleTradingChange('maxRiskPercent', e.target.value)
                  }
                  min="1"
                  max="10"
                />
              </SettingItem>

              <SettingItem>
                <Label>Default Stop Loss (%)</Label>
                <Input
                  type="number"
                  value={trading.defaultStopLoss}
                  onChange={(e) =>
                    handleTradingChange('defaultStopLoss', e.target.value)
                  }
                  min="0.5"
                  step="0.5"
                />
              </SettingItem>

              <SettingItem>
                <Label>Default Take Profit (%)</Label>
                <Input
                  type="number"
                  value={trading.defaultTakeProfit}
                  onChange={(e) =>
                    handleTradingChange('defaultTakeProfit', e.target.value)
                  }
                  min="1"
                  step="0.5"
                />
              </SettingItem>
            </div>

            <SubSection title="Asset Allocation (Should total 100%)">
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 1fr 1fr',
                  gap: 16
                }}
              >
                <SettingItem>
                  <Label>NIFTY 50 Allocation (%)</Label>
                  <Input
                    type="number"
                    value={trading.allocationNifty}
                    onChange={(e) =>
                      handleTradingChange('allocationNifty', e.target.value)
                    }
                    min="0"
                    max="100"
                  />
                </SettingItem>

                <SettingItem>
                  <Label>Bank Nifty Allocation (%)</Label>
                  <Input
                    type="number"
                    value={trading.allocationBankNifty}
                    onChange={(e) =>
                      handleTradingChange('allocationBankNifty', e.target.value)
                    }
                    min="0"
                    max="100"
                  />
                </SettingItem>

                <SettingItem>
                  <Label>Stocks Allocation (%)</Label>
                  <Input
                    type="number"
                    value={trading.allocationStocks}
                    onChange={(e) =>
                      handleTradingChange('allocationStocks', e.target.value)
                    }
                    min="0"
                    max="100"
                  />
                </SettingItem>
              </div>
              <p
                style={{
                  fontSize: 12,
                  color: '#64748b',
                  marginTop: 10,
                  textAlign: 'center'
                }}
              >
                Total:{' '}
                {parseInt(trading.allocationNifty) +
                  parseInt(trading.allocationBankNifty) +
                  parseInt(trading.allocationStocks)}
                %
              </p>
            </SubSection>
          </Section>
        )}

        {/* NOTIFICATIONS */}
        {activeTab === 'notifications' && (
          <Section title="Notifications & Alerts">
            <ToggleSetting
              label="Email Alerts"
              description="Receive price movement alerts via email"
              checked={notifications.emailAlerts}
              onChange={(value) =>
                handleNotificationChange('emailAlerts', value)
              }
            />

            <ToggleSetting
              label="SMS Alerts"
              description="Get critical alerts via SMS"
              checked={notifications.smsAlerts}
              onChange={(value) => handleNotificationChange('smsAlerts', value)}
            />

            <ToggleSetting
              label="Overnight Hold Alert"
              description="Alert before market close about overnight positions"
              checked={notifications.overnightAlert}
              onChange={(value) =>
                handleNotificationChange('overnightAlert', value)
              }
            />

            <ToggleSetting
              label="Price Movement Alert"
              description="Notify on significant price moves"
              checked={notifications.priceAlert}
              onChange={(value) =>
                handleNotificationChange('priceAlert', value)
              }
            />

            <SettingItem>
              <Label>Alert Threshold (%)</Label>
              <Input
                type="number"
                value={notifications.alertThreshold}
                onChange={(e) =>
                  handleNotificationChange('alertThreshold', e.target.value)
                }
                min="1"
                max="20"
              />
              <small style={{ color: '#64748b', marginTop: 4 }}>
                Alert when price moves by this percentage
              </small>
            </SettingItem>
          </Section>
        )}

        {/* DISPLAY SETTINGS */}
        {activeTab === 'display' && (
          <Section title="Display & Theme">
            <SettingItem>
              <Label>Theme</Label>
              <Select
                value={display.theme}
                onChange={(e) => handleDisplayChange('theme', e.target.value)}
              >
                <option value="dark">🌙 Dark (Recommended)</option>
                <option value="light">☀️ Light</option>
              </Select>
            </SettingItem>

            <SettingItem>
              <Label>Chart Type</Label>
              <Select
                value={display.chartType}
                onChange={(e) =>
                  handleDisplayChange('chartType', e.target.value)
                }
              >
                <option value="candlestick">🕯️ Candlestick</option>
                <option value="bar">📊 Bar</option>
                <option value="line">📈 Line</option>
              </Select>
            </SettingItem>

            <SettingItem>
              <Label>Default Timeframe</Label>
              <Select
                value={display.defaultTimeframe}
                onChange={(e) =>
                  handleDisplayChange('defaultTimeframe', e.target.value)
                }
              >
                <option value="1m">1 Minute</option>
                <option value="5m">5 Minutes</option>
                <option value="15m">15 Minutes</option>
                <option value="30m">30 Minutes</option>
                <option value="1h">1 Hour</option>
              </Select>
            </SettingItem>

            <SettingItem>
              <Label>Decimal Places for Prices</Label>
              <Select
                value={display.decimalPlaces}
                onChange={(e) =>
                  handleDisplayChange('decimalPlaces', e.target.value)
                }
              >
                <option value="1">1 decimal place</option>
                <option value="2">2 decimal places</option>
                <option value="3">3 decimal places</option>
              </Select>
            </SettingItem>
          </Section>
        )}

        {/* API SETTINGS - KITE CREDENTIALS */}
        {activeTab === 'api' && (
          <Section title="Kite API Credentials">
            <InfoBox>
              ℹ️ Save your Zerodha Kite API credentials securely. Your
              credentials are encrypted and used for trading orders only. Charts
              and market data continue using the application's shared
              credentials.
            </InfoBox>

            {/* Status */}
            <div
              style={{
                padding: '16px',
                borderRadius: '8px',
                marginBottom: '16px',
                background: kiteCredentials.hasCredentials
                  ? '#065f46'
                  : '#7f1d1d',
                border: `1px solid ${kiteCredentials.hasCredentials ? '#10b981' : '#dc2626'}`,
                color: kiteCredentials.hasCredentials ? '#86efac' : '#fca5a5'
              }}
            >
              <p style={{ margin: 0, fontWeight: 600 }}>
                {kiteCredentials.hasCredentials
                  ? '✅ Credentials Saved'
                  : '⚠️ No Credentials Saved'}
              </p>
              <small style={{ display: 'block', marginTop: 4 }}>
                {kiteCredentials.hasCredentials
                  ? 'Your Kite credentials are securely stored and will be used for trading orders.'
                  : "Without credentials, trading orders will use the application's shared account."}
              </small>
            </div>

            {/* Error/Success Message */}
            {credentialsMessage && (
              <div
                style={{
                  padding: '12px',
                  borderRadius: '8px',
                  marginBottom: '16px',
                  background: credentialsMessage.includes('✅')
                    ? '#065f46'
                    : '#7f1d1d',
                  color: credentialsMessage.includes('✅')
                    ? '#86efac'
                    : '#fca5a5',
                  fontSize: '13px'
                }}
              >
                {credentialsMessage}
              </div>
            )}

            {/* Form */}
            <form
              onSubmit={handleSaveKiteCredentials}
              style={{ marginBottom: 24 }}
            >
              <SettingItem>
                <Label>🔑 API Key</Label>
                <Input
                  type="password"
                  value={kiteCredentials.apiKey}
                  onChange={(e) =>
                    setKiteCredentials((prev) => ({
                      ...prev,
                      apiKey: e.target.value
                    }))
                  }
                  placeholder="Your Zerodha API key"
                  disabled={credentialsLoading}
                />
                <small
                  style={{ color: '#64748b', marginTop: 4, display: 'block' }}
                >
                  Get this from Kite Console → Settings → API Consents
                </small>
              </SettingItem>

              <SettingItem>
                <Label>🎫 24-Hour Access Token</Label>
                <Input
                  type="password"
                  value={kiteCredentials.accessToken}
                  onChange={(e) =>
                    setKiteCredentials((prev) => ({
                      ...prev,
                      accessToken: e.target.value
                    }))
                  }
                  placeholder="Your 24-hour access token"
                  disabled={credentialsLoading}
                />
                <small
                  style={{ color: '#64748b', marginTop: 4, display: 'block' }}
                >
                  Generate this in Kite Console after login. Token expires after
                  24 hours.
                </small>
              </SettingItem>

              <button
                type="submit"
                disabled={credentialsLoading}
                style={{
                  padding: '10px 20px',
                  borderRadius: '6px',
                  border: 'none',
                  background: '#22c55e',
                  color: 'black',
                  cursor: credentialsLoading ? 'not-allowed' : 'pointer',
                  fontWeight: '600',
                  opacity: credentialsLoading ? 0.6 : 1,
                  transition: '0.2s'
                }}
              >
                {credentialsLoading ? '⏳ Saving...' : '💾 Save Credentials'}
              </button>
            </form>

            {/* Instructions */}
            <SubSection title="How to Get Credentials">
              <ol style={{ color: '#cbd5e1', fontSize: 13, lineHeight: 1.8 }}>
                <li>
                  Login to{' '}
                  <a
                    href="https://kite.trade"
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ color: '#22c55e', textDecoration: 'none' }}
                  >
                    Kite Console
                  </a>
                </li>
                <li>
                  Go to <strong>Settings</strong> →{' '}
                  <strong>API Consents</strong>
                </li>
                <li>
                  Copy your <strong>API Key</strong>
                </li>
                <li>
                  Click <strong>Generate Token</strong> to get a new 24-hour
                  access token
                </li>
                <li>Copy the access token (keep it secret!)</li>
                <li>Paste both above and click "Save Credentials"</li>
              </ol>
            </SubSection>

            {/* Change/Delete */}
            {kiteCredentials.hasCredentials && (
              <DangerZone>
                <button
                  onClick={handleDeleteKiteCredentials}
                  disabled={credentialsLoading}
                  style={{
                    ...dangerButtonStyle,
                    opacity: credentialsLoading ? 0.6 : 1,
                    cursor: credentialsLoading ? 'not-allowed' : 'pointer'
                  }}
                >
                  🗑️ {credentialsLoading ? 'Deleting...' : 'Delete Credentials'}
                </button>
                <small
                  style={{ color: '#64748b', marginTop: 8, display: 'block' }}
                >
                  Removes your saved credentials. You can add new ones anytime.
                </small>
              </DangerZone>
            )}

            {/* No Credentials Info */}
            {!kiteCredentials.hasCredentials && (
              <InfoBox>
                ℹ️ <strong>When you provide credentials:</strong> All your
                trading orders will execute under your own Kite account in
                real-time. Without credentials, the app uses shared credentials
                (not recommended for production).
              </InfoBox>
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
      <h2
        style={{
          fontSize: 20,
          fontWeight: 600,
          marginBottom: 20,
          borderBottom: '1px solid #334155',
          paddingBottom: 12
        }}
      >
        {title}
      </h2>
      {children}
    </div>
  );
}

function SubSection({ title, children }) {
  return (
    <div
      style={{
        border: '1px solid #334155',
        borderRadius: 8,
        padding: 16,
        marginBottom: 16
      }}
    >
      <h3
        style={{
          fontSize: 14,
          fontWeight: 600,
          marginBottom: 16,
          color: '#cbd5e1'
        }}
      >
        {title}
      </h3>
      {children}
    </div>
  );
}

function SettingItem({ children }) {
  return <div style={{ marginBottom: 16 }}>{children}</div>;
}

function Label({ children }) {
  return (
    <label
      style={{
        display: 'block',
        fontSize: 14,
        fontWeight: 600,
        marginBottom: 8,
        color: '#cbd5e1'
      }}
    >
      {children}
    </label>
  );
}

function Input({ ...props }) {
  return (
    <input
      {...props}
      style={{
        width: '100%',
        padding: '10px 12px',
        borderRadius: 6,
        border: '1px solid #334155',
        background: '#1e293b',
        color: '#e2e8f0',
        fontSize: 14,
        ...(props.style || {})
      }}
    />
  );
}

function Select({ children, ...props }) {
  return (
    <select
      {...props}
      style={{
        width: '100%',
        padding: '10px 12px',
        borderRadius: 6,
        border: '1px solid #334155',
        background: '#1e293b',
        color: '#e2e8f0',
        fontSize: 14,
        cursor: 'pointer'
      }}
    >
      {children}
    </select>
  );
}

function ToggleSetting({ label, description, checked, onChange }) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 20,
        paddingBottom: 16,
        borderBottom: '1px solid #334155'
      }}
    >
      <div>
        <p style={{ margin: 0, fontWeight: 600, color: '#cbd5e1' }}>{label}</p>
        <small style={{ color: '#64748b', marginTop: 4, display: 'block' }}>
          {description}
        </small>
      </div>
      <label
        style={{
          position: 'relative',
          display: 'inline-block',
          width: 50,
          height: 24
        }}
      >
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          style={{ opacity: 0, width: 0, height: 0 }}
        />
        <span
          style={{
            position: 'absolute',
            cursor: 'pointer',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: checked ? '#22c55e' : '#334155',
            borderRadius: 24,
            transition: '0.3s'
          }}
        />
        <span
          style={{
            position: 'absolute',
            content: '""',
            height: 18,
            width: 18,
            left: checked ? 26 : 3,
            bottom: 3,
            background: 'white',
            borderRadius: '50%',
            transition: '0.3s'
          }}
        />
      </label>
    </div>
  );
}

function InfoBox({ children }) {
  return (
    <div
      style={{
        background: '#065f46',
        border: '1px solid #10b981',
        padding: 12,
        borderRadius: 8,
        marginBottom: 16,
        color: '#86efac',
        fontSize: 13
      }}
    >
      {children}
    </div>
  );
}

function DangerZone({ children }) {
  return (
    <div
      style={{ marginTop: 24, paddingTop: 16, borderTop: '1px solid #334155' }}
    >
      {children}
    </div>
  );
}

const logoutButtonStyle = {
  padding: '10px 16px',
  borderRadius: 6,
  border: '1px solid #ef4444',
  background: 'transparent',
  color: '#ef4444',
  cursor: 'pointer',
  fontWeight: 600,
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  transition: '0.2s'
};

const dangerButtonStyle = {
  padding: '10px 16px',
  borderRadius: 6,
  border: '1px solid #ef4444',
  background: 'transparent',
  color: '#ef4444',
  fontWeight: 600,
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  transition: '0.2s'
};

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

const tabsContainerStyle = {
  display: 'flex',
  gap: 8,
  marginBottom: 24,
  borderBottom: '1px solid #334155',
  overflowX: 'auto'
};

const tabButtonStyle = {
  padding: '12px 16px',
  border: 'none',
  borderRadius: '8px 8px 0 0',
  cursor: 'pointer',
  fontWeight: 600,
  transition: '0.2s',
  whiteSpace: 'nowrap'
};

const contentStyle = {
  background: '#0f172a',
  borderRadius: 12,
  padding: '24px'
};

const sectionStyle = {
  marginBottom: 24
};
