/**
 * Text search and filter utilities for dashboard frontend.
 * Provides functions for filtering and searching data.
 */

/**
 * Search text in object fields
 * @param {Object} item - Item to search
 * @param {string} searchText - Text to search for
 * @param {Array<string>} fields - Fields to search in
 * @returns {boolean} True if search text found in any field
 */
export function searchInFields(item, searchText, fields) {
  if (!searchText || searchText.trim() === '') {
    return true
  }

  const search = searchText.toLowerCase()

  return fields.some(field => {
    const value = getNestedValue(item, field)
    if (value == null) return false

    return String(value).toLowerCase().includes(search)
  })
}

/**
 * Get nested object value by dot-notation path
 * @param {Object} obj - Object to get value from
 * @param {string} path - Dot-notation path (e.g., "user.name")
 * @returns {*} Value at path or undefined
 */
function getNestedValue(obj, path) {
  return path.split('.').reduce((current, key) => current?.[key], obj)
}

/**
 * Filter array by date range
 * @param {Array} items - Items to filter
 * @param {string} dateField - Field name containing date
 * @param {string|null} startDate - Start date (ISO format or null)
 * @param {string|null} endDate - End date (ISO format or null)
 * @returns {Array} Filtered items
 */
export function filterByDateRange(items, dateField, startDate, endDate) {
  return items.filter(item => {
    const itemDate = new Date(getNestedValue(item, dateField))
    if (isNaN(itemDate.getTime())) return true // Keep items with invalid dates

    if (startDate) {
      const start = new Date(startDate)
      if (itemDate < start) return false
    }

    if (endDate) {
      const end = new Date(endDate)
      end.setHours(23, 59, 59, 999) // Include entire end date
      if (itemDate > end) return false
    }

    return true
  })
}

/**
 * Filter array by field value
 * @param {Array} items - Items to filter
 * @param {string} field - Field name to filter by
 * @param {*} value - Value to match (null/undefined = no filter)
 * @returns {Array} Filtered items
 */
export function filterByValue(items, field, value) {
  if (value == null || value === '') {
    return items
  }

  return items.filter(item => {
    const itemValue = getNestedValue(item, field)
    return itemValue === value
  })
}

/**
 * Truncate text to specified length
 * @param {string} text - Text to truncate
 * @param {number} maxLength - Maximum length
 * @param {string} suffix - Suffix to append (default: "...")
 * @returns {string} Truncated text
 */
export function truncateText(text, maxLength = 100, suffix = '...') {
  if (!text || text.length <= maxLength) {
    return text || ''
  }

  return text.substring(0, maxLength - suffix.length) + suffix
}

/**
 * Highlight search text in string
 * @param {string} text - Text to highlight in
 * @param {string} searchText - Text to highlight
 * @returns {string} HTML string with highlighted text
 */
export function highlightText(text, searchText) {
  if (!searchText || !text) {
    return text || ''
  }

  const regex = new RegExp(`(${escapeRegex(searchText)})`, 'gi')
  return text.replace(regex, '<mark>$1</mark>')
}

/**
 * Escape special regex characters
 * @param {string} str - String to escape
 * @returns {string} Escaped string
 */
function escapeRegex(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}
