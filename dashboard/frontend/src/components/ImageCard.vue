<template>
  <div class="image-card" @click="$emit('click', image)">
    <div class="image-container">
      <img
        :src="thumbnailUrl"
        :alt="truncatePrompt(image.prompt)"
        class="thumbnail"
        :class="{ 'is-loaded': imageLoaded }"
        @load="onImageLoad"
        @error="onImageError"
      />
      <div v-if="imageError" class="image-placeholder error">
        <span class="error-icon">⚠️</span>
        <span class="error-text">Failed to load</span>
      </div>
      <div v-if="!imageLoaded && !imageError" class="image-placeholder loading">
        <div class="skeleton"></div>
      </div>

      <div class="image-overlay">
        <p class="prompt-preview">{{ truncatePrompt(image.prompt) }}</p>
      </div>

      <div :class="['status-badge', `status-${image.status}`]">
        {{ statusLabel(image.status) }}
      </div>
    </div>

    <div class="image-info">
      <p class="image-date">{{ formatDate(image.created_at) }}</p>
      <p v-if="image.error_message" class="error-message" :title="image.error_message">
        {{ truncateError(image.error_message) }}
      </p>
    </div>
  </div>
</template>

<script>
import { ref } from 'vue'
import { getThumbnailUrl } from '../services/images'
import { formatDate } from '../utils/date'

export default {
  name: 'ImageCard',
  props: {
    image: {
      type: Object,
      required: true
    }
  },
  emits: ['click'],
  setup(props) {
    const imageLoaded = ref(false)
    const imageError = ref(false)
    const thumbnailUrl = getThumbnailUrl(props.image.id)

    console.log('ImageCard setup:', {
      imageId: props.image.id,
      thumbnailUrl,
      image: props.image
    })

    function onImageLoad() {
      console.log('Image loaded successfully:', thumbnailUrl)
      imageLoaded.value = true
      imageError.value = false
    }

    function onImageError(event) {
      console.error('Image load error:', thumbnailUrl, event)
      imageLoaded.value = false
      imageError.value = true
    }

    function truncatePrompt(prompt) {
      if (!prompt) return 'No prompt'
      if (prompt.length <= 80) return prompt
      return prompt.substring(0, 80) + '...'
    }

    function truncateError(error) {
      if (!error) return ''
      if (error.length <= 50) return error
      return error.substring(0, 50) + '...'
    }

    function statusLabel(status) {
      const labels = {
        'pending': 'Pending',
        'posted': 'Posted',
        'failed': 'Failed'
      }
      return labels[status] || status
    }

    return {
      imageLoaded,
      imageError,
      thumbnailUrl,
      onImageLoad,
      onImageError,
      truncatePrompt,
      truncateError,
      statusLabel,
      formatDate
    }
  }
}
</script>

<style scoped>
.image-card {
  background: white;
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.image-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.image-container {
  position: relative;
  width: 100%;
  padding-bottom: 100%; /* 1:1 aspect ratio */
  background: #f5f5f5;
  overflow: hidden;
}

.thumbnail {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0;
  transition: opacity 0.3s ease-in-out;
}

.thumbnail.is-loaded {
  opacity: 1;
}

.image-placeholder {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 8px;
}

.image-placeholder.loading .skeleton {
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: loading 1.5s infinite;
}

@keyframes loading {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}

.image-placeholder.error {
  background: #fff5f5;
  color: #c53030;
}

.error-icon {
  font-size: 32px;
}

.error-text {
  font-size: 12px;
  font-weight: 500;
}

.image-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: linear-gradient(to top, rgba(0, 0, 0, 0.8), transparent);
  padding: 40px 12px 12px 12px;
  opacity: 0;
  transition: opacity 0.2s;
}

.image-card:hover .image-overlay {
  opacity: 1;
}

.prompt-preview {
  margin: 0;
  color: white;
  font-size: 12px;
  line-height: 1.4;
}

.status-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.status-pending {
  background: #fff3cd;
  color: #856404;
}

.status-posted {
  background: #d4edda;
  color: #155724;
}

.status-failed {
  background: #f8d7da;
  color: #721c24;
}

.image-info {
  padding: 12px;
}

.image-date {
  margin: 0 0 4px 0;
  font-size: 13px;
  color: #666;
}

.error-message {
  margin: 0;
  font-size: 11px;
  color: #c53030;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
