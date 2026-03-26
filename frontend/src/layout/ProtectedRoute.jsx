import { Navigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { getAccessToken, isTokenExpired, refreshToken } from '../utils/auth';

function ProtectedRoute({ children }) {
  const [isAuthorized, setIsAuthorized] = useState(null);

  useEffect(() => {
    const checkAuth = async () => {
      const token = getAccessToken();

      if (!token) {
        setIsAuthorized(false);
        return;
      }

      // Check if token is expired
      if (isTokenExpired(token)) {
        // Try to refresh token
        const refreshed = await refreshToken();
        setIsAuthorized(refreshed);
      } else {
        setIsAuthorized(true);
      }
    };

    checkAuth();
  }, []);

  // Still checking auth
  if (isAuthorized === null) {
    return (
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: '100vh'
        }}
      >
        Loading...
      </div>
    );
  }

  return isAuthorized ? children : <Navigate to="/" />;
}

export default ProtectedRoute;
