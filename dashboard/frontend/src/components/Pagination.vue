<template>
  <div class="pagination">
    <div class="pagination-info">
      <span v-if="total > 0">
        Showing {{ startItem }}-{{ endItem }} of {{ total }} items
      </span>
      <span v-else>No items to display</span>
    </div>

    <div class="pagination-controls">
      <button
        @click="$emit('prev')"
        :disabled="!hasPrevPage"
        class="btn btn-pagination"
        title="Previous page"
      >
        ← Prev
      </button>

      <div class="pagination-pages">
        <button
          v-for="page in visiblePages"
          :key="page"
          @click="$emit('goto', page)"
          :class="['btn btn-pagination', { active: page === currentPage }]"
          :disabled="page === currentPage"
        >
          {{ page }}
        </button>
      </div>

      <button
        @click="$emit('next')"
        :disabled="!hasNextPage"
        class="btn btn-pagination"
        title="Next page"
      >
        Next →
      </button>
    </div>

    <div class="pagination-limit">
      <label for="page-limit">Per page:</label>
      <select
        id="page-limit"
        :value="limit"
        @change="$emit('change-limit', parseInt($event.target.value))"
        class="limit-select"
      >
        <option value="25">25</option>
        <option value="50">50</option>
        <option value="100">100</option>
      </select>
    </div>
  </div>
</template>

<script>
import { computed } from 'vue'

export default {
  name: 'Pagination',
  props: {
    currentPage: {
      type: Number,
      required: true
    },
    totalPages: {
      type: Number,
      required: true
    },
    total: {
      type: Number,
      required: true
    },
    limit: {
      type: Number,
      required: true
    },
    startItem: {
      type: Number,
      required: true
    },
    endItem: {
      type: Number,
      required: true
    },
    hasNextPage: {
      type: Boolean,
      required: true
    },
    hasPrevPage: {
      type: Boolean,
      required: true
    }
  },
  emits: ['next', 'prev', 'goto', 'change-limit'],
  setup(props) {
    // Calculate visible page numbers (max 7 pages shown)
    const visiblePages = computed(() => {
      const pages = []
      const maxVisible = 7
      const { currentPage, totalPages } = props

      if (totalPages <= maxVisible) {
        // Show all pages if total is small
        for (let i = 1; i <= totalPages; i++) {
          pages.push(i)
        }
      } else {
        // Show current page with context
        let start = Math.max(1, currentPage - 3)
        let end = Math.min(totalPages, currentPage + 3)

        // Adjust if near start or end
        if (currentPage <= 4) {
          end = maxVisible
        } else if (currentPage >= totalPages - 3) {
          start = totalPages - maxVisible + 1
        }

        for (let i = start; i <= end; i++) {
          pages.push(i)
        }
      }

      return pages
    })

    return {
      visiblePages
    }
  }
}
</script>

<style scoped>
.pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px;
  background: white;
  border-top: 1px solid #e0e0e0;
  flex-wrap: wrap;
  gap: 15px;
}

.pagination-info {
  color: #666;
  font-size: 14px;
}

.pagination-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pagination-pages {
  display: flex;
  gap: 4px;
}

.btn-pagination {
  padding: 6px 12px;
  border: 1px solid #ddd;
  background: white;
  color: #333;
  border-radius: 4px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
  min-width: 40px;
}

.btn-pagination:hover:not(:disabled) {
  background: #f5f5f5;
  border-color: #667eea;
}

.btn-pagination.active {
  background: #667eea;
  color: white;
  border-color: #667eea;
}

.btn-pagination:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.pagination-limit {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pagination-limit label {
  font-size: 14px;
  color: #666;
}

.limit-select {
  padding: 6px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
  background: white;
  cursor: pointer;
  transition: border-color 0.2s;
}

.limit-select:hover {
  border-color: #667eea;
}

.limit-select:focus {
  outline: none;
  border-color: #667eea;
}

@media (max-width: 768px) {
  .pagination {
    justify-content: center;
  }

  .pagination-info,
  .pagination-limit {
    width: 100%;
    justify-content: center;
  }
}
</style>
