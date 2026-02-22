import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import SwingTrade from './pages/SwingTrade';
import MainLayout from './layout/MainLayout';
import Trades from './pages/Trades';
import History from './pages/History';
import Settings from './pages/Settings';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Login page WITHOUT sidebar */}
        <Route path="/" element={<Login />} />

        {/* All pages WITH sidebar */}
        <Route element={<MainLayout />}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/swing-trade" element={<SwingTrade />} />
          <Route path="/trades" element={<Trades />} />
          <Route path="/history" element={<History />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
