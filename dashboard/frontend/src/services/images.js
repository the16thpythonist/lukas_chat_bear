import api from './api'

/**
 * Get paginated image gallery with optional filters
 * @param {Object} params - Query parameters
 * @param {number} params.page - Page number (default: 1)
 * @param {number} params.limit - Items per page (default: 20, max: 100)
 * @param {string} params.start_date - Filter images after this date (ISO format)
 * @param {string} params.end_date - Filter images before this date (ISO format)
 * @param {string} params.status - Filter by status ('pending', 'posted', 'failed')
 * @returns {Promise<Object>} Paginated images response
 */
export async function getImages(params = {}) {
  try {
    const response = await api.get('/images', { params })
    return response.data
  } catch (error) {
    if (error.response?.data?.message) {
      throw new Error(error.response.data.message)
    }
    throw new Error('Failed to fetch images. Please try again.')
  }
}

/**
 * Get detailed information about a specific image
 * @param {number} imageId - Image ID
 * @returns {Promise<Object>} Image details with full prompt and metadata
 */
export async function getImageDetail(imageId) {
  try {
    const response = await api.get(`/images/${imageId}`)
    return response.data
  } catch (error) {
    if (error.response?.status === 404) {
      throw new Error('Image not found')
    }
    if (error.response?.data?.message) {
      throw new Error(error.response.data.message)
    }
    throw new Error('Failed to fetch image details. Please try again.')
  }
}

/**
 * Get thumbnail URL for an image
 * @param {number} imageId - Image ID
 * @returns {string} Thumbnail URL
 */
export function getThumbnailUrl(imageId) {
  return `${api.defaults.baseURL}/images/${imageId}/thumbnail`
}
