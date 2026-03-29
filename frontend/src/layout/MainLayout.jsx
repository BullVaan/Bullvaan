import Sidebar from './Sidebar';
import { Outlet } from 'react-router-dom';

export default function MainLayout() {
  return (
    <div style={{ display: 'flex', maxWidth: '100vw' }}>
      <Sidebar />

      <div
        style={{
          flex: 1,
          background: '#020617',
          minHeight: '100vh',
          overflowX: 'hidden'
        }}
      >
        <Outlet />
      </div>
    </div>
  );
}
