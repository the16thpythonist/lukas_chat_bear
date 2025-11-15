<template>
  <div class="manual-controls">
    <h1>Manual Controls</h1>
    <p class="subtitle">
      Manually trigger bot actions. All actions are logged and rate-limited.
    </p>

    <!-- Image Generation Control Panel -->
    <ControlPanel
      title="Generate Image"
      :icon="'🎨'"
      :loading="imageLoading"
      :feedback="imageFeedback"
      @submit="handleGenerateImage"
    >
      <template #form>
        <div class="form-group">
          <label for="theme">Theme (optional)</label>
          <input
            id="theme"
            v-model="imageTheme"
            type="text"
            placeholder="e.g., celebration, nature, winter"
            :disabled="imageLoading"
            class="form-control"
          />
          <small class="form-text">
            Optional theme to guide image generation. Leave empty for random theme.
          </small>
        </div>

        <div class="form-group">
          <label for="channel">Target Channel (optional)</label>
          <input
            id="channel"
            v-model="imageChannel"
            type="text"
            placeholder="e.g., C123456 or leave empty for default"
            :disabled="imageLoading"
            class="form-control"
          />
          <small class="form-text">
            Optional Slack channel ID. Leave empty to use bot's default channel.
          </small>
        </div>
      </template>

      <template #actions>
        <button
          type="submit"
          :disabled="imageLoading"
          class="btn btn-primary"
        >
          <span v-if="imageLoading">⏳ Generating...</span>
          <span v-else>🎨 Generate Image</span>
        </button>
      </template>
    </ControlPanel>

    <!-- Random DM Control Panel -->
    <ControlPanel
      title="Send Random DM"
      :icon="'💬'"
      :loading="dmLoading"
      :feedback="dmFeedback"
      @submit="handleSendDM"
    >
      <template #form>
        <div class="form-group">
          <label for="user">Target User (optional)</label>
          <select
            id="user"
            v-model="selectedUserId"
            :disabled="dmLoading || loadingUsers"
            class="form-control"
          >
            <option value="">Random User</option>
            <option
              v-for="user in teamMembers"
              :key="user.slack_user_id"
              :value="user.slack_user_id"
            >
              {{ user.display_name || user.real_name }} ({{ user.slack_user_id }})
            </option>
          </select>
          <small class="form-text">
            Select a specific user or leave as "Random" to let the bot choose.
          </small>
        </div>

        <div v-if="loadingUsers" class="loading-users">
          Loading users...
        </div>
        <div v-else-if="userLoadError" class="error-users">
          ⚠️ Failed to load user list: {{ userLoadError }}
        </div>
      </template>

      <template #actions>
        <button
          type="submit"
          :disabled="dmLoading || loadingUsers"
          class="btn btn-secondary"
        >
          <span v-if="dmLoading">⏳ Sending...</span>
          <span v-else>💬 Send Random DM</span>
        </button>
      </template>
    </ControlPanel>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import ControlPanel from '../components/ControlPanel.vue'
import { generateImage, sendDM } from '../services/controls'
import { getTeamMembers } from '../services/team'

export default {
  name: 'ManualControls',
  components: {
    ControlPanel
  },
  setup() {
    // Image generation state
    const imageTheme = ref('')
    const imageChannel = ref('')
    const imageLoading = ref(false)
    const imageFeedback = ref(null)

    // DM sending state
    const selectedUserId = ref('')
    const dmLoading = ref(false)
    const dmFeedback = ref(null)

    // Team members state
    const teamMembers = ref([])
    const loadingUsers = ref(false)
    const userLoadError = ref(null)

    /**
     * Handle image generation form submission
     */
    async function handleGenerateImage() {
      // Confirmation dialog for cost awareness
      const confirmed = confirm(
        '⚠️ Image Generation Confirmation\n\n' +
        'This will call the OpenAI DALL-E API and may incur costs.\n\n' +
        `Theme: ${imageTheme.value || '(random)'}\n` +
        `Channel: ${imageChannel.value || '(default)'}\n\n` +
        'Are you sure you want to proceed?'
      )

      if (!confirmed) {
        return
      }

      imageLoading.value = true
      imageFeedback.value = null

      try {
        const result = await generateImage(
          imageTheme.value || null,
          imageChannel.value || null
        )

        if (result.success) {
          imageFeedback.value = {
            type: 'success',
            message: result.message,
            details: `Image ID: ${result.image_id}\nPrompt: ${result.prompt}`
          }

          // Clear form on success
          imageTheme.value = ''
          imageChannel.value = ''
        } else {
          imageFeedback.value = {
            type: 'error',
            message: result.message || 'Image generation failed',
            details: result.error
          }
        }
      } catch (error) {
        imageFeedback.value = {
          type: 'error',
          message: error.message || 'Failed to generate image',
          details: error.toString()
        }
      } finally {
        imageLoading.value = false
      }
    }

    /**
     * Handle DM sending form submission
     */
    async function handleSendDM() {
      dmLoading.value = true
      dmFeedback.value = null

      try {
        const result = await sendDM(selectedUserId.value || null)

        if (result.success) {
          dmFeedback.value = {
            type: 'success',
            message: result.message,
            details: `Target User: ${result.target_user}\nPreview: ${result.dm_content}`
          }

          // Clear form on success
          selectedUserId.value = ''
        } else {
          dmFeedback.value = {
            type: 'error',
            message: result.message || 'DM sending failed',
            details: result.error
          }
        }
      } catch (error) {
        dmFeedback.value = {
          type: 'error',
          message: error.message || 'Failed to send DM',
          details: error.toString()
        }
      } finally {
        dmLoading.value = false
      }
    }

    /**
     * Load team members for user selector dropdown
     */
    async function loadTeamMembers() {
      loadingUsers.value = true
      userLoadError.value = null

      try {
        const members = await getTeamMembers()
        teamMembers.value = members
      } catch (error) {
        userLoadError.value = error.message || 'Failed to load users'
        console.error('Failed to load team members:', error)
      } finally {
        loadingUsers.value = false
      }
    }

    // Load team members on mount
    onMounted(() => {
      loadTeamMembers()
    })

    return {
      // Image generation
      imageTheme,
      imageChannel,
      imageLoading,
      imageFeedback,
      handleGenerateImage,

      // DM sending
      selectedUserId,
      dmLoading,
      dmFeedback,
      handleSendDM,

      // Team members
      teamMembers,
      loadingUsers,
      userLoadError
    }
  }
}
</script>

<style scoped>
.manual-controls {
  max-width: 800px;
  margin: 0 auto;
  padding: 2rem;
}

h1 {
  margin-bottom: 0.5rem;
  color: #333;
}

.subtitle {
  color: #666;
  margin-bottom: 2rem;
}

.form-group {
  margin-bottom: 1.5rem;
}

.form-group label {
  display: block;
  font-weight: 600;
  margin-bottom: 0.5rem;
  color: #333;
}

.form-control {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 1rem;
}

.form-control:disabled {
  background-color: #f5f5f5;
  cursor: not-allowed;
}

.form-text {
  display: block;
  margin-top: 0.25rem;
  color: #666;
  font-size: 0.875rem;
}

.btn {
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 4px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.2s;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-primary {
  background-color: #007bff;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background-color: #0056b3;
}

.btn-secondary {
  background-color: #6c757d;
  color: white;
}

.btn-secondary:hover:not(:disabled) {
  background-color: #545b62;
}

.loading-users,
.error-users {
  padding: 0.5rem;
  margin-top: 0.5rem;
  border-radius: 4px;
  font-size: 0.875rem;
}

.loading-users {
  background-color: #e7f3ff;
  color: #004085;
}

.error-users {
  background-color: #f8d7da;
  color: #721c24;
}
</style>
