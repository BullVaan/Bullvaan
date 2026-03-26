// Generic API utilities
// Note: For session-specific functionality, use getAuthHeaders() from auth.js

export function getToken() {
  return localStorage.getItem('token');
}

// Make generic API call
export async function apiCall(endpoint, options = {}) {
  try {
    const response = await fetch(`http://localhost:8000${endpoint}`, options);

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
