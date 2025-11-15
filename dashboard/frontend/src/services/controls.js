/**
 * Manual Controls API Service
 *
 * Provides API calls for manual bot control operations:
 * - Generate and post DALL-E images
 * - Send random proactive DMs
 *
 * All operations require authentication and are rate-limited on the server.
 */

import api from './api'

/**
 * Manually trigger image generation and posting to Slack
 *
 * @param {string|null} theme - Optional theme for image generation (e.g., "celebration", "nature")
 * @param {string|null} channelId - Optional Slack channel ID (e.g., "C123456"). If omitted, uses default channel.
 * @returns {Promise<Object>} Response with success status, message, and image details
 *
 * Success Response:
 * {
 *   success: true,
 *   message: "Image generated and posted successfully to channel C123456",
 *   image_id: 42,
 *   image_url: "file:///app/data/images/abc123.png",
 *   prompt: "A joyful bear celebrating..."
 * }
 *
 * Error Response:
 * {
 *   success: false,
 *   message: "OpenAI API key not configured or invalid",
 *   error: "Detailed error message"
 * }
 *
 * Rate Limit Response (429):
 * {
 *   error: "Rate limit exceeded",
 *   message: "Maximum 10 requests per 60 minutes. Please try again later.",
 *   retry_after_seconds: 1800
 * }
 *
 * @throws {Error} If request fails or server error occurs
 */
export async function generateImage(theme = null, channelId = null) {
  try {
    const response = await api.post('/controls/generate-image', {
      theme: theme || undefined,
      channel_id: channelId || undefined
    })
    return response.data
  } catch (error) {
    // Re-throw with enhanced error message
    if (error.response) {
      // Server responded with error status
      const errorData = error.response.data
      throw new Error(errorData.message || errorData.error || 'Image generation failed')
    } else if (error.request) {
      // Request made but no response received
      throw new Error('No response from server - please check your connection')
    } else {
      // Request setup error
      throw new Error(error.message || 'Failed to send image generation request')
    }
  }
}

/**
 * Manually trigger random DM to a user
 *
 * @param {string|null} userId - Optional Slack user ID (e.g., "U123456"). If omitted, selects random user.
 * @returns {Promise<Object>} Response with success status, message, and DM details
 *
 * Success Response:
 * {
 *   success: true,
 *   message: "Random DM sent successfully to user U123456",
 *   target_user: "U123456",
 *   dm_content: "Hey there! Just wanted to check in..."
 * }
 *
 * Error Response:
 * {
 *   success: false,
 *   message: "No active users available to send DM",
 *   error: "Detailed error message"
 * }
 *
 * Rate Limit Response (429):
 * {
 *   error: "Rate limit exceeded",
 *   message: "Maximum 20 requests per 60 minutes. Please try again later.",
 *   retry_after_seconds: 1200
 * }
 *
 * @throws {Error} If request fails or server error occurs
 */
export async function sendDM(userId = null) {
  try {
    const response = await api.post('/controls/send-dm', {
      user_id: userId || undefined
    })
    return response.data
  } catch (error) {
    // Re-throw with enhanced error message
    if (error.response) {
      // Server responded with error status
      const errorData = error.response.data
      throw new Error(errorData.message || errorData.error || 'DM sending failed')
    } else if (error.request) {
      // Request made but no response received
      throw new Error('No response from server - please check your connection')
    } else {
      // Request setup error
      throw new Error(error.message || 'Failed to send DM request')
    }
  }
}

export default {
  generateImage,
  sendDM
}
