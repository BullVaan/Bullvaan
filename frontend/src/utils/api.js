// Generic API utilities
// Note: For session-specific functionality, use getAuthHeaders() from auth.js

export const API_BASE_URL =
  process.env.REACT_APP_API_URL || 'http://localhost:8000';

// Derive WebSocket URL from API_BASE_URL (http→ws, https→wss)
export const getWsUrl = (path) => {
  const base = API_BASE_URL.replace(/^https/, 'wss').replace(/^http/, 'ws');
  return `${base}${path}`;
};

export function getToken() {
  return localStorage.getItem('token');
}

// Make generic API call
export async function apiCall(endpoint, options = {}) {
  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, options);

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error(`API Error [${endpoint}]:`, error.message);
    throw error;
  }
}
