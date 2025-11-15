import { ref, computed } from 'vue'

/**
 * Composable for managing pagination state
 * @param {number} initialPage - Initial page number (default: 1)
 * @param {number} initialLimit - Initial items per page (default: 50)
 * @returns {Object} Pagination state and methods
 */
export function usePagination(initialPage = 1, initialLimit = 50) {
  const currentPage = ref(initialPage)
  const limit = ref(initialLimit)
  const total = ref(0)
  const totalPages = ref(0)

  // Computed properties
  const hasNextPage = computed(() => currentPage.value < totalPages.value)
  const hasPrevPage = computed(() => currentPage.value > 1)
  const startItem = computed(() => (currentPage.value - 1) * limit.value + 1)
  const endItem = computed(() => Math.min(currentPage.value * limit.value, total.value))

  /**
   * Update pagination metadata from API response
   * @param {Object} response - API response with pagination metadata
   */
  function updatePagination(response) {
    if (response.page) currentPage.value = response.page
    if (response.limit) limit.value = response.limit
    if (response.total !== undefined) total.value = response.total
    if (response.pages) totalPages.value = response.pages
  }

  /**
   * Go to next page
   */
  function nextPage() {
    if (hasNextPage.value) {
      currentPage.value++
    }
  }

  /**
   * Go to previous page
   */
  function prevPage() {
    if (hasPrevPage.value) {
      currentPage.value--
    }
  }

  /**
   * Go to specific page
   * @param {number} page - Page number to navigate to
   */
  function goToPage(page) {
    if (page >= 1 && page <= totalPages.value) {
      currentPage.value = page
    }
  }

  /**
   * Change items per page limit
   * @param {number} newLimit - New limit value
   */
  function changeLimit(newLimit) {
    limit.value = newLimit
    currentPage.value = 1 // Reset to first page when changing limit
  }

  /**
   * Reset pagination to initial state
   */
  function reset() {
    currentPage.value = initialPage
    limit.value = initialLimit
    total.value = 0
    totalPages.value = 0
  }

  return {
    // State
    currentPage,
    limit,
    total,
    totalPages,

    // Computed
    hasNextPage,
    hasPrevPage,
    startItem,
    endItem,

    // Methods
    updatePagination,
    nextPage,
    prevPage,
    goToPage,
    changeLimit,
    reset
  }
}
