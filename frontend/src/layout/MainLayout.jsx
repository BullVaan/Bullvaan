import Sidebar from './Sidebar';
import AppBar from './AppBar';
import Footer from './Footer';
import { Outlet } from 'react-router-dom';

export default function MainLayout() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <AppBar />
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <Sidebar />
        <div
          style={{
            flex: 1,
            background: '#020617',
            overflowX: 'hidden',
            overflowY: 'auto'
          }}
        >
          <Outlet />
        </div>
      </div>
      <Footer />
    </div>
  );
}
