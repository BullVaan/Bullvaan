import Sidebar from '../components/Sidebar';

export default function MainLayout({ children }) {
  return (
    <div style={{ display: 'flex', overflow: 'hidden', maxWidth: '100vw' }}>
      <Sidebar />
      <div style={{ flex: 1, background: '#020617', minHeight: '100vh', overflow: 'hidden' }}>
        {children}
      </div>
    </div>
  );
}
