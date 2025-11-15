import api from './api'

/**
 * Login with password
 * @param {string} password - Admin password
 * @returns {Promise<boolean>} True if login successful
 */
export async function login(password) {
  try {
    const response = await api.post('/auth/login', { password })
    return response.data.success
  } catch (error) {
    if (error.response?.data?.message) {
      throw new Error(error.response.data.message)
    }
    throw new Error('Login failed. Please try again.')
  }
}

/**
 * Logout and clear session
 * @returns {Promise<boolean>} True if logout successful
 */
export async function logout() {
  try {
    const response = await api.post('/auth/logout')
    return response.data.success
  } catch (error) {
    console.error('Logout error:', error)
    return false
  }
}

/**
 * Check current session status
 * @returns {Promise<Object>} Session information
 */
export async function checkSession() {
  try {
    const response = await api.get('/auth/session')
    return response.data
  } catch (error) {
    return { authenticated: false, session: null }
  }
}
