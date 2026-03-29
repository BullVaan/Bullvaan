import { Outlet } from 'react-router-dom';
import AppBar from './AppBar';
import Footer from './Footer';

export default function PublicLayout() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <AppBar />
      <div style={{ flex: 1, overflowY: 'auto', background: '#020617' }}>
        <Outlet />
      </div>
      <Footer />
    </div>
  );
}
