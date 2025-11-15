<template>
  <div class="activity-log">
    <div class="page-header">
      <h2>Activity Log</h2>
      <p class="page-description">View all messages sent by Lukas</p>
    </div>

    <div class="filters-section">
      <div class="filters-grid">
        <div class="filter-group">
          <label for="start-date">Start Date</label>
          <input
            id="start-date"
            v-model="filters.start_date"
            type="datetime-local"
            class="filter-input"
          />
        </div>

        <div class="filter-group">
          <label for="end-date">End Date</label>
          <input
            id="end-date"
            v-model="filters.end_date"
            type="datetime-local"
            class="filter-input"
          />
        </div>

        <div class="filter-group">
          <label for="channel-type">Channel Type</label>
          <select
            id="channel-type"
            v-model="filters.channel_type"
            class="filter-input"
          >
            <option value="">All Types</option>
            <option value="dm">Direct Messages</option>
            <option value="channel">Channels</option>
            <option value="thread">Threads</option>
          </select>
        </div>

        <div class="filter-group">
          <label for="recipient">Recipient (User ID)</label>
          <input
            id="recipient"
            v-model="filters.recipient"
            type="text"
            placeholder="e.g., U12345678"
            class="filter-input"
          />
        </div>
      </div>

      <div class="filters-actions">
        <button @click="applyFilters" class="btn btn-primary">
          Apply Filters
        </button>
        <button @click="clearFilters" class="btn btn-secondary">
          Clear Filters
        </button>
        <button
          @click="fetchActivity"
          class="btn btn-secondary"
          :disabled="loading || isRefreshing"
          title="Refresh data"
        >
          🔄 Refresh
        </button>
        <div class="auto-refresh-indicator">
          <span
            v-if="isPolling && !isPaused"
            :class="['status-indicator', 'active', { 'refreshing': isRefreshing }]"
          ></span>
          <span v-else class="status-indicator"></span>
          <span class="status-text">
            {{ isRefreshing ? 'Updating...' : (isPolling && !isPaused ? 'Auto-refresh on' : 'Paused') }}
          </span>
        </div>
      </div>
    </div>

    <ActivityTable
      :items="items"
      :loading="loading && isInitialLoad"
      :error="error"
      @retry="fetchActivity"
    />

    <Pagination
      v-if="items.length > 0"
      :current-page="currentPage"
      :total-pages="totalPages"
      :total="total"
      :limit="limit"
      :start-item="startItem"
      :end-item="endItem"
      :has-next-page="hasNextPage"
      :has-prev-page="hasPrevPage"
      @next="handleNextPage"
      @prev="handlePrevPage"
      @goto="handleGoToPage"
      @change-limit="handleChangeLimit"
    />
  </div>
</template>

<script>
import { ref, watch, nextTick } from 'vue'
import { getActivityLog } from '../services/activity'
import { usePagination } from '../composables/usePagination'
import { usePolling } from '../composables/usePolling'
import ActivityTable from '../components/ActivityTable.vue'
import Pagination from '../components/Pagination.vue'

export default {
  name: 'ActivityLog',
  components: {
    ActivityTable,
    Pagination
  },
  setup() {
    // State
    const items = ref([])
    const loading = ref(false)
    const error = ref('')
    const isInitialLoad = ref(true)
    const isRefreshing = ref(false)

    // Filters
    const filters = ref({
      start_date: '',
      end_date: '',
      channel_type: '',
      recipient: ''
    })

    const appliedFilters = ref({})

    // Pagination
    const {
      currentPage,
      limit,
      total,
      totalPages,
      hasNextPage,
      hasPrevPage,
      startItem,
      endItem,
      updatePagination,
      nextPage,
      prevPage,
      goToPage,
      changeLimit,
      reset: resetPagination
    } = usePagination(1, 50)

    // Fetch activity data
    async function fetchActivity(preserveScroll = false) {
      // Save scroll position if requested (for polling updates)
      let scrollPosition = 0
      if (preserveScroll) {
        scrollPosition = window.scrollY || window.pageYOffset
        isRefreshing.value = true
      } else {
        loading.value = true
      }

      error.value = ''

      try {
        const params = {
          page: currentPage.value,
          limit: limit.value,
          ...appliedFilters.value
        }

        const response = await getActivityLog(params)

        // Check if data actually changed to avoid unnecessary re-renders
        const newItemsJson = JSON.stringify(response.items)
        const currentItemsJson = JSON.stringify(items.value)

        if (newItemsJson !== currentItemsJson) {
          items.value = response.items || []
          updatePagination(response)
        }
      } catch (err) {
        error.value = err.message || 'Failed to load activity log'
        if (!preserveScroll) {
          items.value = []
        }
      } finally {
        loading.value = false
        isRefreshing.value = false
        isInitialLoad.value = false

        // Restore scroll position after Vue has fully updated the DOM
        if (preserveScroll && scrollPosition > 0) {
          // Wait for Vue to finish rendering, then wait one more frame
          await nextTick()
          requestAnimationFrame(() => {
            window.scrollTo(0, scrollPosition)
          })
        }
      }
    }

    // Polling for auto-refresh (with scroll preservation)
    const { isPolling, isPaused } = usePolling(() => fetchActivity(true), 10000, true)

    // Apply filters
    function applyFilters() {
      // Convert datetime-local to ISO format for API
      const formatted = {}
      if (filters.value.start_date) {
        formatted.start_date = new Date(filters.value.start_date).toISOString()
      }
      if (filters.value.end_date) {
        formatted.end_date = new Date(filters.value.end_date).toISOString()
      }
      if (filters.value.channel_type) {
        formatted.channel_type = filters.value.channel_type
      }
      if (filters.value.recipient) {
        formatted.recipient = filters.value.recipient.trim()
      }

      appliedFilters.value = formatted
      resetPagination()
      fetchActivity()
    }

    // Clear filters
    function clearFilters() {
      filters.value = {
        start_date: '',
        end_date: '',
        channel_type: '',
        recipient: ''
      }
      appliedFilters.value = {}
      resetPagination()
      fetchActivity()
    }

    // Pagination handlers
    function handleNextPage() {
      nextPage()
    }

    function handlePrevPage() {
      prevPage()
    }

    function handleGoToPage(page) {
      goToPage(page)
    }

    function handleChangeLimit(newLimit) {
      changeLimit(newLimit)
    }

    // Watch for pagination changes
    watch([currentPage, limit], () => {
      fetchActivity()
    })

    return {
      // Data
      items,
      loading,
      error,
      isInitialLoad,
      isRefreshing,

      // Filters
      filters,
      applyFilters,
      clearFilters,

      // Pagination
      currentPage,
      limit,
      total,
      totalPages,
      hasNextPage,
      hasPrevPage,
      startItem,
      endItem,
      handleNextPage,
      handlePrevPage,
      handleGoToPage,
      handleChangeLimit,

      // Polling
      isPolling,
      isPaused,

      // Methods
      fetchActivity
    }
  }
}
</script>

<style scoped>
.activity-log {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page-header {
  background: white;
  padding: 24px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.page-header h2 {
  margin: 0 0 8px 0;
  font-size: 24px;
  color: #333;
}

.page-description {
  margin: 0;
  color: #666;
  font-size: 14px;
}

.filters-section {
  background: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.filters-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.filter-group label {
  font-size: 13px;
  font-weight: 600;
  color: #555;
}

.filter-input {
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
  transition: border-color 0.2s;
}

.filter-input:focus {
  outline: none;
  border-color: #667eea;
}

.filters-actions {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.auto-refresh-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
  padding: 8px 12px;
  background: #f5f5f5;
  border-radius: 4px;
}

.status-indicator {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #ccc;
}

.status-indicator.active {
  background: #4caf50;
  animation: pulse 2s infinite;
}

.status-indicator.active.refreshing {
  background: #667eea;
  animation: pulse-fast 0.8s infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

@keyframes pulse-fast {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.6;
    transform: scale(1.1);
  }
}

.status-text {
  font-size: 13px;
  color: #666;
}

@media (max-width: 768px) {
  .filters-grid {
    grid-template-columns: 1fr;
  }

  .auto-refresh-indicator {
    margin-left: 0;
  }
}
</style>
