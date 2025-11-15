/**
 * Scheduled Events API Service
 *
 * Handles API calls for scheduled channel messages.
 * Proxied through dashboard backend to bot internal API.
 */

import api from './api'

/**
 * List scheduled events with optional filtering
 * @param {Object} params - Query parameters
 * @param {string} params.status - Filter by status (pending, completed, cancelled, failed)
 * @param {number} params.limit - Maximum number of results
 * @param {number} params.offset - Skip N results
 * @returns {Promise<Object>} Response with events array
 */
export async function listScheduledEvents({ status, limit = 100, offset = 0 } = {}) {
  const params = {}
  if (status) params.status = status
  if (limit) params.limit = limit
  if (offset) params.offset = offset

  const response = await api.get('/scheduled-events', { params })
  return response.data
}

/**
 * Create a new scheduled event
 * @param {Object} eventData - Event data
 * @param {string} eventData.target_channel_id - Channel ID or name
 * @param {string} eventData.target_channel_name - Channel display name
 * @param {string} eventData.scheduled_time - ISO datetime string
 * @param {string} eventData.message - Message content
 * @param {string} eventData.created_by_user_id - Optional: Creator user ID
 * @param {string} eventData.created_by_user_name - Optional: Creator name
 * @returns {Promise<Object>} Created event
 */
export async function createScheduledEvent(eventData) {
  const response = await api.post('/scheduled-events', eventData)
  return response.data
}

/**
 * Get a specific scheduled event
 * @param {number} eventId - Event ID
 * @returns {Promise<Object>} Event details
 */
export async function getScheduledEvent(eventId) {
  const response = await api.get(`/scheduled-events/${eventId}`)
  return response.data
}

/**
 * Update a scheduled event
 * @param {number} eventId - Event ID to update
 * @param {Object} updates - Fields to update
 * @param {string} updates.scheduled_time - Optional: New scheduled time (ISO string)
 * @param {string} updates.message - Optional: New message content
 * @returns {Promise<Object>} Updated event
 */
export async function updateScheduledEvent(eventId, updates) {
  const response = await api.put(`/scheduled-events/${eventId}`, updates)
  return response.data
}

/**
 * Cancel a pending scheduled event
 * @param {number} eventId - Event ID to cancel
 * @returns {Promise<Object>} Success response
 */
export async function cancelScheduledEvent(eventId) {
  const response = await api.delete(`/scheduled-events/${eventId}`)
  return response.data
}

/**
 * List ALL scheduled events (unified view)
 * Includes user-created channel messages AND system recurring tasks
 * @param {Object} params - Query parameters
 * @param {string} params.status - Filter by status (pending, completed, cancelled, failed)
 * @param {number} params.limit - Maximum number of results
 * @returns {Promise<Object>} Response with unified events array
 */
export async function listAllScheduledEvents({ status, limit = 100 } = {}) {
  const params = {}
  if (status) params.status = status
  if (limit) params.limit = limit

  const response = await api.get('/scheduled-events/all', { params })
  return response.data
}

/**
 * Cancel a recurring task (Random DM or Image Post)
 * @param {string} jobName - Job name (random_dm_task or image_post_task)
 * @returns {Promise<Object>} Success response
 */
export async function cancelRecurringTask(jobName) {
  const response = await api.delete(`/scheduled-events/recurring-task/${jobName}`)
  return response.data
}
