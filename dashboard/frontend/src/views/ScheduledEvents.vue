<template>
  <div class="scheduled-events">
    <div class="header">
      <h2>Scheduled Messages</h2>
      <button @click="showCreateForm = true" class="btn-primary">
        + Schedule New Message
      </button>
    </div>

    <!-- Create/Edit Form Modal -->
    <div v-if="showCreateForm || editingEvent" class="modal-overlay" @click.self="closeForm">
      <div class="modal-content">
        <div class="modal-header">
          <h3>{{ editingEvent ? 'Edit Scheduled Message' : 'Schedule New Message' }}</h3>
          <button @click="closeForm" class="close-btn">&times;</button>
        </div>

        <form @submit.prevent="submitForm" class="event-form">
          <div class="form-group">
            <label for="channel">Channel *</label>
            <input
              id="channel"
              v-model="formData.channel"
              type="text"
              required
              placeholder="#general or C123456"
              :disabled="!!editingEvent"
            />
            <small>Enter channel name (with or without #) or channel ID</small>
          </div>

          <div class="form-group">
            <label for="scheduled_time">Scheduled Time (UTC) *</label>
            <input
              id="scheduled_time"
              v-model="formData.scheduled_time"
              type="datetime-local"
              required
            />
            <small>Select when the message should be posted</small>
          </div>

          <div class="form-group">
            <label for="message">Message *</label>
            <textarea
              id="message"
              v-model="formData.message"
              required
              rows="4"
              placeholder="Enter the message to post..."
            />
          </div>

          <div v-if="formError" class="error-message">
            {{ formError }}
          </div>

          <div class="form-actions">
            <button type="button" @click="closeForm" class="btn-secondary">
              Cancel
            </button>
            <button type="submit" class="btn-primary" :disabled="formSubmitting">
              {{ formSubmitting ? 'Saving...' : (editingEvent ? 'Update' : 'Schedule') }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- Filters -->
    <div class="filters">
      <label>
        <input type="radio" v-model="statusFilter" value="pending" />
        Pending
      </label>
      <label>
        <input type="radio" v-model="statusFilter" value="completed" />
        Completed
      </label>
      <label>
        <input type="radio" v-model="statusFilter" value="cancelled" />
        Cancelled
      </label>
      <label>
        <input type="radio" v-model="statusFilter" value="failed" />
        Failed
      </label>
      <label>
        <input type="radio" v-model="statusFilter" value="" />
        All
      </label>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="loading-spinner">
      Loading scheduled messages...
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="error-message">
      <p>Error: {{ error }}</p>
      <button @click="loadEvents" class="retry-button">Retry</button>
    </div>

    <!-- Empty State -->
    <div v-else-if="!events || events.length === 0" class="empty-state">
      <p>No {{ statusFilter || 'scheduled' }} messages found.</p>
      <button v-if="statusFilter === 'pending' || !statusFilter" @click="showCreateForm = true" class="btn-primary">
        Schedule Your First Message
      </button>
    </div>

    <!-- Events Table -->
    <div v-else class="events-table-container">
      <table class="events-table">
        <thead>
          <tr>
            <th>Type</th>
            <th>Target</th>
            <th>Scheduled Time</th>
            <th>Message/Action</th>
            <th>Recurrence</th>
            <th>Status</th>
            <th>Created By</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="event in events" :key="event.id" :class="'status-' + event.status">
            <td>
              <span :class="['type-badge', getTypeBadgeClass(event.type)]">
                {{ getTypeIcon(event.type) }} {{ event.type_display }}
              </span>
            </td>
            <td>{{ event.target }}</td>
            <td>{{ formatDateTime(event.scheduled_time) }}</td>
            <td class="message-cell" :title="event.message">
              {{ truncateMessage(event.message) }}
            </td>
            <td>
              <span v-if="event.is_recurring" class="recurrence-badge">
                {{ event.recurrence_info }}
              </span>
              <span v-else class="recurrence-once">One-time</span>
            </td>
            <td>
              <span :class="'status-badge status-' + event.status">
                {{ event.status }}
              </span>
            </td>
            <td>{{ event.created_by }}</td>
            <td class="actions-cell">
              <!-- Edit button: Only for pending channel messages -->
              <button
                v-if="event.can_edit && event.status === 'pending'"
                @click="startEdit(event)"
                class="btn-icon"
                title="Edit"
              >
                ✏️
              </button>
              <!-- Cancel button: For all pending events -->
              <button
                v-if="event.can_cancel && event.status === 'pending'"
                @click="confirmCancel(event)"
                class="btn-icon btn-danger"
                :title="event.is_recurring ? 'Stop recurring task' : 'Cancel event'"
              >
                ❌
              </button>
              <span v-if="event.status !== 'pending'" class="no-actions">-</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Confirm Cancel Dialog -->
    <div v-if="cancelingEvent" class="modal-overlay" @click.self="cancelingEvent = null">
      <div class="modal-content modal-small">
        <h3>{{ cancelingEvent.is_recurring ? 'Stop Recurring Task?' : 'Cancel Scheduled Message?' }}</h3>
        <p v-if="cancelingEvent.is_recurring">
          This will permanently stop this recurring task. No future occurrences will be created.
        </p>
        <p v-else>
          Are you sure you want to cancel this scheduled message?
        </p>
        <p class="cancel-details">
          <strong>Type:</strong> {{ cancelingEvent.type_display }}<br/>
          <strong>Target:</strong> {{ cancelingEvent.target }}<br/>
          <strong>Time:</strong> {{ formatDateTime(cancelingEvent.scheduled_time) }}<br/>
          <strong v-if="cancelingEvent.is_recurring">Recurrence:</strong>
          <span v-if="cancelingEvent.is_recurring">{{ cancelingEvent.recurrence_info }}</span><br v-if="cancelingEvent.is_recurring"/>
          <strong>{{ cancelingEvent.is_recurring ? 'Action' : 'Message' }}:</strong> {{ truncateMessage(cancelingEvent.message, 100) }}
        </p>
        <div class="form-actions">
          <button @click="cancelingEvent = null" class="btn-secondary">
            {{ cancelingEvent.is_recurring ? 'Keep Task' : 'Keep Event' }}
          </button>
          <button @click="executeCancel" class="btn-danger" :disabled="formSubmitting">
            {{ formSubmitting ? 'Cancelling...' : (cancelingEvent.is_recurring ? 'Yes, Stop Task' : 'Yes, Cancel Event') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, watch } from 'vue'
import {
  listAllScheduledEvents,
  createScheduledEvent,
  updateScheduledEvent,
  cancelScheduledEvent,
  cancelRecurringTask
} from '@/services/scheduledEvents.js'
import { formatDateTime } from '@/utils/date'

export default {
  name: 'ScheduledEvents',
  setup() {
    // State
    const events = ref([])
    const loading = ref(false)
    const error = ref(null)
    const statusFilter = ref('pending')

    // Form state
    const showCreateForm = ref(false)
    const editingEvent = ref(null)
    const formData = ref({
      channel: '',
      scheduled_time: '',
      message: ''
    })
    const formError = ref(null)
    const formSubmitting = ref(false)

    // Cancel confirmation state
    const cancelingEvent = ref(null)

    // Load events (unified view - includes recurring tasks)
    const loadEvents = async () => {
      loading.value = true
      error.value = null

      try {
        const response = await listAllScheduledEvents({
          status: statusFilter.value || undefined,
          limit: 100
        })
        events.value = response.events || []
      } catch (err) {
        console.error('Error loading scheduled events:', err)
        error.value = err.response?.data?.error || 'Failed to load scheduled events'
      } finally {
        loading.value = false
      }
    }

    // Watch status filter changes
    watch(statusFilter, () => {
      loadEvents()
    })

    // Close form
    const closeForm = () => {
      showCreateForm.value = false
      editingEvent.value = null
      formData.value = {
        channel: '',
        scheduled_time: '',
        message: ''
      }
      formError.value = null
    }

    // Submit form (create or update)
    const submitForm = async () => {
      formError.value = null
      formSubmitting.value = true

      try {
        // Convert datetime-local to ISO string
        const scheduledTime = new Date(formData.value.scheduled_time).toISOString()

        if (editingEvent.value) {
          // Update existing event (extract numeric ID from event_123 format)
          const eventId = editingEvent.value._raw_id
          await updateScheduledEvent(eventId, {
            scheduled_time: scheduledTime,
            message: formData.value.message
          })
        } else {
          // Create new event
          await createScheduledEvent({
            target_channel_id: formData.value.channel,
            target_channel_name: formData.value.channel.startsWith('#') ? formData.value.channel : `#${formData.value.channel}`,
            scheduled_time: scheduledTime,
            message: formData.value.message
          })
        }

        closeForm()
        loadEvents()
      } catch (err) {
        console.error('Error submitting form:', err)
        formError.value = err.response?.data?.error || 'Failed to save scheduled event'
      } finally {
        formSubmitting.value = false
      }
    }

    // Start editing an event (only for channel messages)
    const startEdit = (event) => {
      // Only allow editing channel messages
      if (event.type !== 'channel_message') {
        error.value = 'Only channel messages can be edited'
        return
      }

      editingEvent.value = event
      // Convert UTC datetime to local datetime-local format
      const localDateTime = new Date(event.scheduled_time + 'Z')
        .toISOString()
        .slice(0, 16)

      formData.value = {
        channel: event.target,
        scheduled_time: localDateTime,
        message: event.message
      }
      formError.value = null
    }

    // Confirm cancel
    const confirmCancel = (event) => {
      cancelingEvent.value = event
    }

    // Execute cancel
    const executeCancel = async () => {
      if (!cancelingEvent.value) return

      formSubmitting.value = true
      try {
        const event = cancelingEvent.value

        // Check if this is a recurring task or regular event
        if (event.is_recurring && event.job_name) {
          // Cancel recurring task (stops future occurrences)
          await cancelRecurringTask(event.job_name)
        } else {
          // Cancel single event (extract numeric ID from event_123 format)
          const eventId = event._raw_id
          await cancelScheduledEvent(eventId)
        }

        cancelingEvent.value = null
        loadEvents()
      } catch (err) {
        console.error('Error cancelling event:', err)
        error.value = err.response?.data?.error || 'Failed to cancel event'
      } finally {
        formSubmitting.value = false
      }
    }

    // Utility functions
    const truncateMessage = (message, maxLength = 80) => {
      if (!message) return ''
      return message.length > maxLength
        ? message.substring(0, maxLength) + '...'
        : message
    }

    // Get type badge class for styling
    const getTypeBadgeClass = (type) => {
      const classes = {
        'channel_message': 'type-channel',
        'random_dm': 'type-dm',
        'image_post': 'type-image'
      }
      return classes[type] || 'type-default'
    }

    // Get type icon
    const getTypeIcon = (type) => {
      const icons = {
        'channel_message': '💬',
        'random_dm': '🎲',
        'image_post': '🖼️'
      }
      return icons[type] || '📅'
    }

    // Load events on mount
    onMounted(() => {
      loadEvents()
    })

    return {
      events,
      loading,
      error,
      statusFilter,
      showCreateForm,
      editingEvent,
      formData,
      formError,
      formSubmitting,
      cancelingEvent,
      loadEvents,
      closeForm,
      submitForm,
      startEdit,
      confirmCancel,
      executeCancel,
      formatDateTime,
      truncateMessage,
      getTypeBadgeClass,
      getTypeIcon
    }
  }
}
</script>

<style scoped>
.scheduled-events {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header h2 {
  margin: 0;
}

/* Buttons */
.btn-primary,
.btn-secondary,
.btn-danger {
  padding: 10px 20px;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.btn-primary {
  background-color: #007bff;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background-color: #0056b3;
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-secondary {
  background-color: #6c757d;
  color: white;
}

.btn-secondary:hover {
  background-color: #5a6268;
}

.btn-danger {
  background-color: #dc3545;
  color: white;
}

.btn-danger:hover:not(:disabled) {
  background-color: #c82333;
}

.btn-icon {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  padding: 4px 8px;
}

.btn-icon:hover {
  opacity: 0.7;
}

/* Filters */
.filters {
  display: flex;
  gap: 20px;
  margin-bottom: 20px;
  padding: 15px;
  background-color: #f8f9fa;
  border-radius: 4px;
}

.filters label {
  display: flex;
  align-items: center;
  gap: 5px;
  cursor: pointer;
}

/* Loading, error, empty states */
.loading-spinner {
  text-align: center;
  padding: 40px;
  color: #666;
}

.error-message {
  background-color: #fee;
  border: 1px solid #fcc;
  padding: 15px;
  border-radius: 4px;
  color: #c33;
  margin-bottom: 20px;
}

.retry-button {
  margin-top: 10px;
  padding: 8px 16px;
  background-color: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: #999;
}

.empty-state p {
  margin-bottom: 20px;
  font-size: 16px;
}

/* Table */
.events-table-container {
  background-color: white;
  border-radius: 4px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  overflow-x: auto;
}

.events-table {
  width: 100%;
  border-collapse: collapse;
}

.events-table thead {
  background-color: #f8f9fa;
}

.events-table th,
.events-table td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid #dee2e6;
}

.events-table th {
  font-weight: 600;
  color: #495057;
}

.events-table tbody tr:hover {
  background-color: #f8f9fa;
}

.message-cell {
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.actions-cell {
  white-space: nowrap;
}

.no-actions {
  color: #999;
}

/* Status badges */
.status-badge {
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
}

.status-badge.status-pending {
  background-color: #fff3cd;
  color: #856404;
}

.status-badge.status-completed {
  background-color: #d4edda;
  color: #155724;
}

.status-badge.status-failed {
  background-color: #f8d7da;
  color: #721c24;
}

.status-badge.status-cancelled {
  background-color: #d1ecf1;
  color: #0c5460;
}

/* Modal */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background-color: white;
  padding: 30px;
  border-radius: 8px;
  max-width: 600px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-small {
  max-width: 400px;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.modal-header h3 {
  margin: 0;
}

.close-btn {
  background: none;
  border: none;
  font-size: 28px;
  cursor: pointer;
  color: #999;
  line-height: 1;
}

.close-btn:hover {
  color: #333;
}

/* Form */
.event-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.form-group label {
  font-weight: 600;
  color: #495057;
}

.form-group input,
.form-group textarea {
  padding: 10px;
  border: 1px solid #ced4da;
  border-radius: 4px;
  font-size: 14px;
}

.form-group input:focus,
.form-group textarea:focus {
  outline: none;
  border-color: #007bff;
}

.form-group small {
  color: #6c757d;
  font-size: 12px;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 10px;
}

.cancel-details {
  background-color: #f8f9fa;
  padding: 15px;
  border-radius: 4px;
  margin: 15px 0;
  line-height: 1.8;
}

/* Type badges */
.type-badge {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.type-badge.type-channel {
  background-color: #e3f2fd;
  color: #1976d2;
}

.type-badge.type-dm {
  background-color: #f3e5f5;
  color: #7b1fa2;
}

.type-badge.type-image {
  background-color: #fff3e0;
  color: #f57c00;
}

.type-badge.type-default {
  background-color: #f5f5f5;
  color: #616161;
}

/* Recurrence badges */
.recurrence-badge {
  display: inline-block;
  padding: 3px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
  background-color: #e8f5e9;
  color: #2e7d32;
}

.recurrence-once {
  color: #999;
  font-size: 12px;
}
</style>
