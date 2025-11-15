/**
 * Team Members API Service
 *
 * Provides API calls for fetching team member information
 * Used for user selection in manual controls (DM target dropdown)
 */

import api from './api'

/**
 * Get list of active team members
 *
 * @returns {Promise<Array>} Array of team member objects
 *
 * Response format:
 * [
 *   {
 *     slack_user_id: "U123456",
 *     display_name: "John Doe",
 *     real_name: "John Doe",
 *     message_count: 42
 *   },
 *   ...
 * ]
 *
 * @throws {Error} If request fails or server error occurs
 */
export async function getTeamMembers() {
  try {
    const response = await api.get('/team')
    return response.data
  } catch (error) {
    console.error('Failed to fetch team members:', error)
    throw new Error(
      error.response?.data?.message ||
      error.message ||
      'Failed to load team members'
    )
  }
}

export default {
  getTeamMembers
}
