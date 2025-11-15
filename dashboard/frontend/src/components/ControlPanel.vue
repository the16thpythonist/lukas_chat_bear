<template>
  <div class="control-panel">
    <div class="panel-header">
      <h2>
        <span class="icon">{{ icon }}</span>
        {{ title }}
      </h2>
    </div>

    <form @submit.prevent="handleSubmit" class="panel-body">
      <!-- Form fields slot -->
      <div class="form-section">
        <slot name="form"></slot>
      </div>

      <!-- Feedback display -->
      <div v-if="feedback" :class="['feedback', `feedback-${feedback.type}`]">
        <div class="feedback-message">
          <strong v-if="feedback.type === 'success'">✓ Success:</strong>
          <strong v-else>✗ Error:</strong>
          {{ feedback.message }}
        </div>
        <div v-if="feedback.details" class="feedback-details">
          {{ feedback.details }}
        </div>
      </div>

      <!-- Action buttons slot -->
      <div class="actions-section">
        <slot name="actions"></slot>
      </div>
    </form>
  </div>
</template>

<script>
export default {
  name: 'ControlPanel',
  props: {
    /**
     * Panel title text
     */
    title: {
      type: String,
      required: true
    },

    /**
     * Icon emoji to display next to title
     */
    icon: {
      type: String,
      default: '⚙️'
    },

    /**
     * Loading state (disables form)
     */
    loading: {
      type: Boolean,
      default: false
    },

    /**
     * Feedback object to display success/error messages
     * Format: { type: 'success'|'error', message: string, details?: string }
     */
    feedback: {
      type: Object,
      default: null,
      validator: (value) => {
        if (!value) return true
        return (
          ['success', 'error'].includes(value.type) &&
          typeof value.message === 'string'
        )
      }
    }
  },

  emits: ['submit'],

  setup(props, { emit }) {
    /**
     * Handle form submission
     * Emits 'submit' event to parent component
     */
    function handleSubmit() {
      if (!props.loading) {
        emit('submit')
      }
    }

    return {
      handleSubmit
    }
  }
}
</script>

<style scoped>
.control-panel {
  background: white;
  border: 1px solid #ddd;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  margin-bottom: 2rem;
  overflow: hidden;
}

.panel-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 1.5rem;
  color: white;
}

.panel-header h2 {
  margin: 0;
  font-size: 1.5rem;
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.icon {
  font-size: 2rem;
}

.panel-body {
  padding: 2rem;
}

.form-section {
  margin-bottom: 1.5rem;
}

.feedback {
  padding: 1rem;
  border-radius: 4px;
  margin-bottom: 1.5rem;
  border: 1px solid;
}

.feedback-success {
  background-color: #d4edda;
  border-color: #c3e6cb;
  color: #155724;
}

.feedback-error {
  background-color: #f8d7da;
  border-color: #f5c6cb;
  color: #721c24;
}

.feedback-message {
  font-weight: 600;
  margin-bottom: 0.5rem;
}

.feedback-details {
  font-size: 0.875rem;
  opacity: 0.9;
  white-space: pre-wrap;
  word-break: break-word;
}

.actions-section {
  display: flex;
  gap: 1rem;
  justify-content: flex-start;
}
</style>
