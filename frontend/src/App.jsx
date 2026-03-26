import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Login from './pages/Login';
import Signup from './pages/Signup';
import Dashboard from './pages/Dashboard';
import SwingTrade from './pages/SwingTrade';
import MainLayout from './layout/MainLayout';
import Trades from './pages/Trades';
import ActiveOrders from './pages/ActiveOrders';
import History from './pages/History';
import Settings from './pages/Settings';
import ProtectedRoute from './layout/ProtectedRoute';
import CandlesCharts from './pages/CandlesCharts';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Login page WITHOUT sidebar */}
        <Route path="/" element={<Login />} />
        <Route path="/signup" element={<Signup />} />

        {/* All pages WITH sidebar */}
        <Route element={<MainLayout />}>
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/swing-trade"
            element={
              <ProtectedRoute>
                <SwingTrade />
              </ProtectedRoute>
            }
          />
          <Route
            path="/trades"
            element={
              <ProtectedRoute>
                <ActiveOrders />
              </ProtectedRoute>
            }
          />
          <Route
            path="/trades-history"
            element={
              <ProtectedRoute>
                <Trades />
              </ProtectedRoute>
            }
          />
          <Route
            path="/history"
            element={
              <ProtectedRoute>
                <History />
              </ProtectedRoute>
            }
          />
          <Route
            path="/settings"
            element={
              <ProtectedRoute>
                <Settings />
              </ProtectedRoute>
            }
          />
          <Route
            path="/candles-charts"
            element={
              <ProtectedRoute>
                <CandlesCharts />
              </ProtectedRoute>
            }
          />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
