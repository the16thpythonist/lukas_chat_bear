import { ref, onMounted, onUnmounted } from 'vue'

/**
 * Composable for polling/auto-refresh functionality
 * Automatically pauses when page is hidden and resumes when visible
 *
 * @param {Function} callback - Function to call on each poll
 * @param {number} interval - Polling interval in milliseconds (default: 10000 = 10s)
 * @param {boolean} immediate - Whether to call callback immediately on mount (default: true)
 * @returns {Object} Polling state and controls
 */
export function usePolling(callback, interval = 10000, immediate = true) {
  const isPolling = ref(false)
  const isPaused = ref(false)
  let intervalId = null

  /**
   * Start polling
   */
  function start() {
    if (isPolling.value) return

    isPolling.value = true
    isPaused.value = false

    // Call immediately if requested
    if (immediate) {
      callback()
    }

    // Set up interval
    intervalId = setInterval(() => {
      if (!isPaused.value) {
        callback()
      }
    }, interval)
  }

  /**
   * Stop polling
   */
  function stop() {
    if (intervalId) {
      clearInterval(intervalId)
      intervalId = null
    }
    isPolling.value = false
    isPaused.value = false
  }

  /**
   * Pause polling (keeps interval but doesn't call callback)
   */
  function pause() {
    isPaused.value = true
  }

  /**
   * Resume polling
   */
  function resume() {
    isPaused.value = false
  }

  /**
   * Manually trigger a poll immediately
   */
  function poll() {
    callback()
  }

  /**
   * Handle page visibility change
   * Pause when page is hidden, resume when visible
   */
  function handleVisibilityChange() {
    if (document.hidden) {
      pause()
    } else {
      resume()
      // Trigger immediate poll when page becomes visible again
      if (isPolling.value) {
        poll()
      }
    }
  }

  // Set up lifecycle hooks
  onMounted(() => {
    // Listen for page visibility changes
    document.addEventListener('visibilitychange', handleVisibilityChange)

    // Start polling on mount
    start()
  })

  onUnmounted(() => {
    // Clean up
    document.removeEventListener('visibilitychange', handleVisibilityChange)
    stop()
  })

  return {
    // State
    isPolling,
    isPaused,

    // Methods
    start,
    stop,
    pause,
    resume,
    poll
  }
}
