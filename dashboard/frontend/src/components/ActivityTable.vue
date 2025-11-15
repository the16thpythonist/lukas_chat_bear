<template>
  <div class="activity-table">
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>Loading activity log...</p>
    </div>

    <div v-else-if="error" class="error-state">
      <p class="error-message">{{ error }}</p>
      <button @click="$emit('retry')" class="btn btn-secondary">Retry</button>
    </div>

    <div v-else-if="items.length === 0" class="empty-state">
      <p>No messages found</p>
      <p class="empty-hint">Try adjusting your filters or date range</p>
    </div>

    <div v-else class="table-wrapper">
      <table>
        <thead>
          <tr>
            <th>Timestamp</th>
            <th>User</th>
            <th>Channel</th>
            <th>Message</th>
            <th>Tokens</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="item in items" :key="item.id">
            <tr :class="{ expanded: expandedId === item.id }">
              <td>{{ formatDate(item.timestamp) }}</td>
              <td>
                <div class="user-info">
                  <div class="user-name">{{ item.display_name || 'Unknown' }}</div>
                  <div v-if="item.real_name" class="user-real-name">
                    {{ item.real_name }}
                  </div>
                </div>
              </td>
              <td>
                <span :class="['channel-type', `type-${item.channel_type}`]">
                  {{ item.channel_type }}
                </span>
              </td>
              <td>
                <div class="message-preview">
                  {{ truncateMessage(item.content, 100) }}
                </div>
              </td>
              <td>
                <span class="token-count">{{ item.token_count || 0 }}</span>
              </td>
              <td>
                <button
                  @click="toggleExpand(item.id)"
                  class="btn btn-sm"
                  :title="expandedId === item.id ? 'Collapse' : 'Expand'"
                >
                  {{ expandedId === item.id ? '▲' : '▼' }}
                </button>
              </td>
            </tr>
            <tr v-if="expandedId === item.id" :key="`detail-${item.id}`" class="detail-row">
              <td colspan="6">
                <div class="message-detail">
                  <div v-if="detailLoading" class="detail-loading">
                    <div class="spinner-sm"></div>
                    Loading details...
                  </div>
                  <div v-else-if="detailError" class="detail-error">
                    {{ detailError }}
                  </div>
                  <div v-else-if="detailData" class="detail-content">
                    <div class="detail-section">
                      <h4>Full Message</h4>
                      <pre class="message-full">{{ detailData.content }}</pre>
                    </div>

                    <div class="detail-section">
                      <h4>Conversation Context</h4>
                      <div class="context-messages">
                        <div
                          v-for="msg in detailData.context"
                          :key="msg.id"
                          :class="['context-message', `sender-${msg.sender}`]"
                        >
                          <div class="context-header">
                            <span class="context-sender">{{ msg.sender }}</span>
                            <span class="context-time">{{ formatDate(msg.timestamp) }}</span>
                          </div>
                          <div class="context-content">{{ msg.content }}</div>
                        </div>
                      </div>
                    </div>

                    <div class="detail-section">
                      <h4>Metadata</h4>
                      <div class="metadata-grid">
                        <div class="metadata-item">
                          <span class="metadata-label">Conversation ID:</span>
                          <span class="metadata-value">{{ detailData.conversation.id }}</span>
                        </div>
                        <div class="metadata-item">
                          <span class="metadata-label">Channel ID:</span>
                          <span class="metadata-value">{{ detailData.conversation.channel_id }}</span>
                        </div>
                        <div class="metadata-item">
                          <span class="metadata-label">Started:</span>
                          <span class="metadata-value">{{ formatDate(detailData.conversation.started_at) }}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script>
import { ref, watch } from 'vue'
import { formatDate } from '../utils/date'
import { getActivityDetail } from '../services/activity'

export default {
  name: 'ActivityTable',
  props: {
    items: {
      type: Array,
      required: true
    },
    loading: {
      type: Boolean,
      default: false
    },
    error: {
      type: String,
      default: ''
    }
  },
  emits: ['retry'],
  setup(props) {
    const expandedId = ref(null)
    const detailData = ref(null)
    const detailLoading = ref(false)
    const detailError = ref('')

    // Truncate message for preview
    function truncateMessage(text, maxLength) {
      if (!text) return ''
      if (text.length <= maxLength) return text
      return text.substring(0, maxLength) + '...'
    }

    // Toggle expand/collapse
    async function toggleExpand(id) {
      if (expandedId.value === id) {
        // Collapse
        expandedId.value = null
        detailData.value = null
        detailError.value = ''
      } else {
        // Expand
        expandedId.value = id
        detailLoading.value = true
        detailError.value = ''

        try {
          detailData.value = await getActivityDetail(id)
        } catch (error) {
          detailError.value = error.message || 'Failed to load message details'
        } finally {
          detailLoading.value = false
        }
      }
    }

    // Reset expanded state when items change
    watch(() => props.items, () => {
      expandedId.value = null
      detailData.value = null
      detailError.value = ''
    })

    return {
      expandedId,
      detailData,
      detailLoading,
      detailError,
      formatDate,
      truncateMessage,
      toggleExpand
    }
  }
}
</script>

<style scoped>
.activity-table {
  background: white;
  border-radius: 8px;
  overflow: hidden;
  /* CSS containment for better performance */
  contain: layout style paint;
  will-change: contents;
}

/* Loading/Error/Empty States */
.loading-state,
.error-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: #666;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid #f3f3f3;
  border-top: 4px solid #667eea;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 15px;
}

.spinner-sm {
  width: 20px;
  height: 20px;
  border: 3px solid #f3f3f3;
  border-top: 3px solid #667eea;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  display: inline-block;
  margin-right: 10px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.empty-hint {
  font-size: 14px;
  color: #999;
  margin-top: 5px;
}

/* Table Styles */
.table-wrapper {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
}

thead {
  background: #f8f9fa;
  border-bottom: 2px solid #e0e0e0;
}

th {
  padding: 12px;
  text-align: left;
  font-weight: 600;
  font-size: 13px;
  color: #555;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

tbody tr {
  border-bottom: 1px solid #e0e0e0;
  transition: background-color 0.2s ease-out;
  /* Improve rendering performance */
  contain: layout style;
}

tbody tr:hover {
  background-color: #f8f9fa;
}

tbody tr.expanded {
  background-color: #f0f4ff;
}

td {
  padding: 12px;
  font-size: 14px;
  color: #333;
  vertical-align: top;
  /* Prevent layout shifts */
  contain: layout style;
}

/* User Info */
.user-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.user-name {
  font-weight: 500;
}

.user-real-name {
  font-size: 12px;
  color: #666;
}

/* Channel Type Badge */
.channel-type {
  display: inline-block;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.type-dm {
  background: #e3f2fd;
  color: #1976d2;
}

.type-channel {
  background: #f3e5f5;
  color: #7b1fa2;
}

.type-thread {
  background: #fff3e0;
  color: #f57c00;
}

/* Message Preview */
.message-preview {
  max-width: 400px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Token Count */
.token-count {
  font-weight: 500;
  color: #667eea;
}

/* Detail Row */
.detail-row {
  background: #fafbfc;
}

.detail-row td {
  padding: 0;
}

.message-detail {
  padding: 20px;
}

.detail-loading,
.detail-error {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  color: #666;
}

.detail-error {
  color: #d32f2f;
}

.detail-section {
  margin-bottom: 24px;
}

.detail-section:last-child {
  margin-bottom: 0;
}

.detail-section h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 600;
  color: #555;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.message-full {
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  padding: 12px;
  font-family: 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-wrap: break-word;
  overflow-x: auto;
  max-height: 400px;
}

/* Context Messages */
.context-messages {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.context-message {
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  padding: 12px;
}

.context-message.sender-user {
  border-left: 3px solid #4caf50;
}

.context-message.sender-assistant {
  border-left: 3px solid #667eea;
}

.context-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 12px;
}

.context-sender {
  font-weight: 600;
  color: #555;
  text-transform: capitalize;
}

.context-time {
  color: #999;
}

.context-content {
  font-size: 13px;
  color: #333;
  line-height: 1.5;
}

/* Metadata Grid */
.metadata-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 12px;
}

.metadata-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.metadata-label {
  font-size: 12px;
  font-weight: 600;
  color: #666;
  text-transform: uppercase;
}

.metadata-value {
  font-size: 14px;
  color: #333;
  font-family: 'Courier New', monospace;
}

/* Buttons */
.btn-sm {
  padding: 4px 12px;
  font-size: 12px;
}

@media (max-width: 768px) {
  .message-preview {
    max-width: 200px;
  }

  th, td {
    padding: 8px;
    font-size: 12px;
  }
}
</style>
