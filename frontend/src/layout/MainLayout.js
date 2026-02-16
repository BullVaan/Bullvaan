import Sidebar from '../components/Sidebar';

export default function MainLayout({ children }) {
  return (
    <div style={{ display: 'flex' }}>
      {' '}
      <Sidebar />
      <div style={{ flex: 1, background: '#020617', minHeight: '100vh' }}>
        {children}
      </div>
    </div>
  );
}
