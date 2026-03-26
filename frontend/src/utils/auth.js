// Frontend authentication utilities for JWT token management
import { apiCall } from './api';

/**
 * Get the stored JWT access token from localStorage
 */
export const getAccessToken = () => {
  return localStorage.getItem('access_token');
};

/**
 * Save JWT access token to localStorage
 */
export const setAccessToken = (token) => {
  localStorage.setItem('access_token', token);
};

/**
 * Remove JWT token from localStorage and clear auth data
 */
export const clearAccessToken = () => {
  localStorage.removeItem('access_token');
  localStorage.removeItem('user_id');
  localStorage.removeItem('email');
};

/**
 * Get current user ID from localStorage
 */
export const getUserId = () => {
  return localStorage.getItem('user_id');
};

/**
 * Get current user email from localStorage
 */
export const getUserEmail = () => {
  return localStorage.getItem('email');
};

/**
 * Check if user is authenticated (has access token)
 */
export const isAuthenticated = () => {
  return !!getAccessToken();
};

/**
 * Get or create a unique session ID for this browser/tab
 * Persists in localStorage so same session survives page reloads
 */
export const getOrCreateSessionId = () => {
  let sessionId = localStorage.getItem('sessionId');
  if (!sessionId) {
    sessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    localStorage.setItem('sessionId', sessionId);
  }
  return sessionId;
};

/**
 * Add Authorization header with Bearer token to fetch headers
 * Also includes X-Session-ID for multi-session auto-trading support
 */
export const getAuthHeaders = () => {
  const token = getAccessToken();
  const sessionId = getOrCreateSessionId();
  return {
    'Content-Type': 'application/json',
    ...(token && { Authorization: `Bearer ${token}` }),
    'X-Session-ID': sessionId
  };
};

/**
 * Parse JWT token payload (without verification - done on backend)
 * Useful for checking expiration client-side
 */
export const parseToken = (token) => {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload);
  } catch (e) {
    return null;
  }
};

/**
 * Check if JWT token is expired
 */
export const isTokenExpired = (token) => {
  if (!token) return true;
  const payload = parseToken(token);
  if (!payload || !payload.exp) return true;
  // Token is expired if current time is past expiration time
  return Date.now() / 1000 > payload.exp;
};

/**
 * Refresh JWT token by calling /api/refresh-token endpoint
 */
export const refreshToken = async () => {
  try {
    const data = await apiCall('/api/refresh-token', {
      method: 'POST',
      headers: getAuthHeaders()
    });

    if (data.access_token) {
      setAccessToken(data.access_token);
      return true;
    }
    return false;
  } catch (error) {
    console.error('Token refresh failed:', error);
    clearAccessToken();
    return false;
  }
};

/**
 * Logout by clearing token and redirecting to login
 */
export const logout = () => {
  clearAccessToken();
  // Redirect will be handled by ProtectedRoute or caller
};
