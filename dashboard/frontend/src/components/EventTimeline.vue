<template>
  <div class="event-timeline">
    <div
      v-for="event in events"
      :key="event.id"
      class="timeline-item"
    >
      <!-- Icon based on event type -->
      <div class="timeline-icon" :class="'icon-' + getEventIconClass(event.task_type)">
        {{ getEventIcon(event.task_type) }}
      </div>

      <!-- Event details -->
      <div class="timeline-content">
        <div class="event-header">
          <h4 class="event-type">{{ formatEventType(event.task_type) }}</h4>
          <span class="event-time">{{ formatScheduledTime(event.scheduled_time) }}</span>
        </div>

        <div class="event-body">
          <!-- Target information -->
          <div v-if="event.target_type && event.target_id" class="event-target">
            <strong>Target:</strong> {{ formatTarget(event.target_type, event.target_id) }}
          </div>

          <!-- Metadata information -->
          <div v-if="event.metadata" class="event-metadata">
            <strong>Details:</strong> {{ formatMetadata(event.metadata) }}
          </div>

          <!-- Time until scheduled -->
          <div class="event-countdown">
            {{ getCountdown(event.scheduled_time) }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { formatDateTime } from '@/utils/date'

export default {
  name: 'EventTimeline',
  props: {
    events: {
      type: Array,
      required: true,
      default: () => []
    }
  },
  setup() {
    // Format event type for display
    const formatEventType = (taskType) => {
      const typeMap = {
        'reminder': 'Reminder',
        'random_dm': 'Random DM',
        'image_post': 'Scheduled Image',
        'manual_image': 'Manual Image',
        'manual_dm': 'Manual DM'
      }
      return typeMap[taskType] || taskType
    }

    // Get icon for event type
    const getEventIcon = (taskType) => {
      const iconMap = {
        'reminder': '⏰',
        'random_dm': '💬',
        'image_post': '🖼️',
        'manual_image': '🎨',
        'manual_dm': '📤'
      }
      return iconMap[taskType] || '📅'
    }

    // Get icon class for styling
    const getEventIconClass = (taskType) => {
      const classMap = {
        'reminder': 'reminder',
        'random_dm': 'dm',
        'image_post': 'image',
        'manual_image': 'image',
        'manual_dm': 'dm'
      }
      return classMap[taskType] || 'default'
    }

    // Format scheduled time
    const formatScheduledTime = (timestamp) => {
      if (!timestamp) return 'No time set'
      return formatDateTime(timestamp)
    }

    // Format target information
    const formatTarget = (targetType, targetId) => {
      if (targetType === 'user') {
        return `User ${targetId}`
      } else if (targetType === 'channel') {
        return `Channel ${targetId}`
      }
      return `${targetType}: ${targetId}`
    }

    // Format metadata
    const formatMetadata = (metadata) => {
      if (typeof metadata === 'string') {
        try {
          metadata = JSON.parse(metadata)
        } catch (e) {
          return metadata
        }
      }

      // Handle interval_hours
      if (metadata.interval_hours !== undefined) {
        const hours = metadata.interval_hours
        if (hours < 1) {
          const minutes = Math.round(hours * 60)
          return `Repeats every ${minutes} minute${minutes !== 1 ? 's' : ''}`
        } else if (hours === 24) {
          return 'Repeats daily'
        } else if (hours % 24 === 0) {
          const days = hours / 24
          return `Repeats every ${days} day${days !== 1 ? 's' : ''}`
        } else {
          return `Repeats every ${hours} hour${hours !== 1 ? 's' : ''}`
        }
      }

      // Handle interval_days
      if (metadata.interval_days !== undefined) {
        const days = metadata.interval_days
        if (days === 1) {
          return 'Repeats daily'
        } else if (days === 7) {
          return 'Repeats weekly'
        } else if (days === 30) {
          return 'Repeats monthly'
        } else {
          return `Repeats every ${days} day${days !== 1 ? 's' : ''}`
        }
      }

      // Handle theme
      if (metadata.theme) {
        return `Theme: ${metadata.theme}`
      }

      // Handle target_user
      if (metadata.target_user) {
        return `Target user: ${metadata.target_user}`
      }

      // Handle message for reminders
      if (metadata.message) {
        return `Message: "${metadata.message}"`
      }

      // Fallback: show key-value pairs in a readable format
      const entries = Object.entries(metadata)
      if (entries.length === 0) {
        return null
      }

      return entries
        .map(([key, value]) => `${key}: ${value}`)
        .join(', ')
    }

    // Get countdown until scheduled time
    const getCountdown = (scheduledTime) => {
      if (!scheduledTime) return ''

      const scheduled = new Date(scheduledTime)
      const now = new Date()
      const diff = scheduled - now

      if (diff < 0) {
        return 'Overdue'
      }

      const minutes = Math.floor(diff / 1000 / 60)
      const hours = Math.floor(minutes / 60)
      const days = Math.floor(hours / 24)

      if (days > 0) {
        return `in ${days} day${days > 1 ? 's' : ''}`
      } else if (hours > 0) {
        return `in ${hours} hour${hours > 1 ? 's' : ''}`
      } else if (minutes > 0) {
        return `in ${minutes} minute${minutes > 1 ? 's' : ''}`
      } else {
        return 'in less than a minute'
      }
    }

    return {
      formatEventType,
      getEventIcon,
      getEventIconClass,
      formatScheduledTime,
      formatTarget,
      formatMetadata,
      getCountdown
    }
  }
}
</script>

<style scoped>
.event-timeline {
  position: relative;
  padding-left: 60px;
}

.event-timeline::before {
  content: '';
  position: absolute;
  left: 20px;
  top: 0;
  bottom: 0;
  width: 2px;
  background-color: #e0e0e0;
}

.timeline-item {
  position: relative;
  margin-bottom: 30px;
}

.timeline-icon {
  position: absolute;
  left: -50px;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  background-color: #dbdbdb;
  z-index: 1;
}

.timeline-content {
  background-color: white;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 15px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.event-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.event-type {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.event-time {
  font-size: 14px;
  color: #666;
}

.event-body {
  font-size: 14px;
  color: #555;
}

.event-target,
.event-metadata {
  margin-bottom: 5px;
}

.event-countdown {
  margin-top: 10px;
  font-size: 13px;
  color: #999;
  font-style: italic;
}
</style>
