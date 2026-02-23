import Sidebar from '../components/Sidebar';
import { Outlet } from 'react-router-dom';

export default function MainLayout() {
  return (
    <div
      style={{
        display: 'flex',
        maxWidth: '100vw',
        minHeight: '100vh',
        background: '#0f172a'
      }}
    >
      <Sidebar />

      <div
        style={{
          flex: 1,
          minHeight: '100vh',
          padding: '36px 24px 24px 24px',
          background: 'linear-gradient(180deg, #1e293b 0%, #020617 100%)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center'
        }}
      >
        <div
          style={{
            width: '100%',
            maxWidth: 1100,
            background: 'rgba(2,6,23,0.98)',
            borderRadius: 18,
            boxShadow: '0 4px 32px 0 rgba(20,30,60,0.10)',
            padding: '32px 28px',
            marginTop: 12,
            minHeight: 600
          }}
        >
          <Outlet />
        </div>
      </div>
    </div>
  );
}
