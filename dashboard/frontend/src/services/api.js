import axios from 'axios'

// Create axios instance with default configuration
const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 30000, // 30 second timeout
  withCredentials: true, // Include cookies for session management
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor
api.interceptors.request.use(
  (config) => {
    // Add any request transformations here
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor for global error handling
api.interceptors.response.use(
  (response) => {
    return response
  },
  (error) => {
    // Handle authentication errors
    if (error.response?.status === 401) {
      // Redirect to login if not authenticated
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }

    // Handle rate limiting
    if (error.response?.status === 429) {
      console.warn('Rate limit exceeded')
    }

    // Log errors in development
    if (import.meta.env.DEV) {
      console.error('API Error:', error.response?.data || error.message)
    }

    return Promise.reject(error)
  }
)

export default api
