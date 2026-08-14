import { useState } from 'react';
import Sidebar from '../components/Sidebar';
import { Outlet } from 'react-router-dom';

export default function MainLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(true);

  return (
    <div style={{ display: 'flex', maxWidth: '100vw' }}>
      <Sidebar open={sidebarOpen} setOpen={setSidebarOpen} />

      <div
        style={{
          flex: 1,
          background: '#020617',
          minHeight: '100vh',
          overflowX: 'hidden',
          marginLeft: sidebarOpen ? 220 : 80,
          transition: 'margin-left 0.3s'
        }}
      >
        <Outlet />
      </div>
    </div>
  );
}
