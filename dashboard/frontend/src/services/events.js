/**
 * Events Service
 *
 * API calls for scheduled events (upcoming and completed).
 * Implements T070 requirement.
 */

import api from './api'

/**
 * Get upcoming (pending) scheduled events.
 *
 * @param {number} limit - Maximum number of events to return (default: 50)
 * @returns {Promise} API response with upcoming events
 */
export async function getUpcomingEvents(limit = 50) {
  const response = await api.get('/events/upcoming', {
    params: { limit }
  })
  return response.data
}

/**
 * Get completed scheduled events (paginated).
 *
 * @param {number} page - Page number (1-indexed)
 * @param {number} limit - Items per page (default: 50)
 * @returns {Promise} API response with paginated completed events
 */
export async function getCompletedEvents(page = 1, limit = 50) {
  const response = await api.get('/events/completed', {
    params: { page, limit }
  })
  return response.data
}
