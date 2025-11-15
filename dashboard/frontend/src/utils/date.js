/**
 * Date formatting utilities for dashboard frontend.
 * Converts ISO timestamps to human-readable formats.
 */

/**
 * Format ISO date string to local datetime string
 * @param {string} isoString - ISO format date string
 * @returns {string} Formatted date string (e.g., "2025-10-28 14:30:00")
 */
export function formatDateTime(isoString) {
  if (!isoString) return ''

  const date = new Date(isoString)
  if (isNaN(date.getTime())) return isoString

  return date.toLocaleString('en-US', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  })
}

/**
 * Format ISO date string to local date only
 * @param {string} isoString - ISO format date string
 * @returns {string} Formatted date string (e.g., "2025-10-28")
 */
export function formatDate(isoString) {
  if (!isoString) return ''

  const date = new Date(isoString)
  if (isNaN(date.getTime())) return isoString

  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  })
}

/**
 * Format ISO date string to relative time (e.g., "2 hours ago")
 * @param {string} isoString - ISO format date string
 * @returns {string} Relative time string
 */
export function formatRelativeTime(isoString) {
  if (!isoString) return ''

  const date = new Date(isoString)
  if (isNaN(date.getTime())) return isoString

  const now = new Date()
  const diffMs = now - date
  const diffSec = Math.floor(diffMs / 1000)
  const diffMin = Math.floor(diffSec / 60)
  const diffHour = Math.floor(diffMin / 60)
  const diffDay = Math.floor(diffHour / 24)

  if (diffSec < 60) {
    return 'just now'
  } else if (diffMin < 60) {
    return `${diffMin} minute${diffMin !== 1 ? 's' : ''} ago`
  } else if (diffHour < 24) {
    return `${diffHour} hour${diffHour !== 1 ? 's' : ''} ago`
  } else if (diffDay < 7) {
    return `${diffDay} day${diffDay !== 1 ? 's' : ''} ago`
  } else {
    return formatDate(isoString)
  }
}

/**
 * Get current date in ISO format for date inputs
 * @returns {string} Current date in YYYY-MM-DD format
 */
export function getCurrentDate() {
  const now = new Date()
  return now.toISOString().split('T')[0]
}

/**
 * Get date N days ago in ISO format
 * @param {number} days - Number of days ago
 * @returns {string} Date in YYYY-MM-DD format
 */
export function getDaysAgo(days) {
  const date = new Date()
  date.setDate(date.getDate() - days)
  return date.toISOString().split('T')[0]
}
