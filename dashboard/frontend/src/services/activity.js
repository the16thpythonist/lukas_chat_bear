import api from './api'

/**
 * Get paginated activity log with optional filters
 * @param {Object} params - Query parameters
 * @param {number} params.page - Page number (default: 1)
 * @param {number} params.limit - Items per page (default: 50, max: 100)
 * @param {string} params.start_date - Filter messages after this date (ISO format)
 * @param {string} params.end_date - Filter messages before this date (ISO format)
 * @param {string} params.recipient - Filter by user_id
 * @param {string} params.channel_type - Filter by channel type ('dm', 'channel', 'thread')
 * @returns {Promise<Object>} Paginated activity log response
 */
export async function getActivityLog(params = {}) {
  try {
    const response = await api.get('/activity', { params })
    return response.data
  } catch (error) {
    if (error.response?.data?.message) {
      throw new Error(error.response.data.message)
    }
    throw new Error('Failed to fetch activity log. Please try again.')
  }
}

/**
 * Get detailed information about a specific message
 * @param {number} messageId - Message ID
 * @returns {Promise<Object>} Message details with conversation context
 */
export async function getActivityDetail(messageId) {
  try {
    const response = await api.get(`/activity/${messageId}`)
    return response.data
  } catch (error) {
    if (error.response?.status === 404) {
      throw new Error('Message not found')
    }
    if (error.response?.data?.message) {
      throw new Error(error.response.data.message)
    }
    throw new Error('Failed to fetch message details. Please try again.')
  }
}
