<template>
  <div class="login-container">
    <div class="login-card">
      <h1>Lukas Dashboard</h1>
      <p class="subtitle">Admin Login</p>

      <form @submit.prevent="handleLogin">
        <div class="form-group">
          <label for="password">Password</label>
          <input
            id="password"
            v-model="password"
            type="password"
            placeholder="Enter admin password"
            required
            :disabled="loading"
          />
        </div>

        <div v-if="error" class="error-message">
          {{ error }}
        </div>

        <button type="submit" class="btn btn-primary" :disabled="loading">
          {{ loading ? 'Logging in...' : 'Login' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { login } from '../services/auth'

export default {
  name: 'Login',
  setup() {
    const router = useRouter()
    const password = ref('')
    const loading = ref(false)
    const error = ref('')

    const handleLogin = async () => {
      error.value = ''
      loading.value = true

      try {
        const success = await login(password.value)
        if (success) {
          router.push('/activity')
        }
      } catch (err) {
        error.value = err.message || 'Login failed. Please check your password.'
      } finally {
        loading.value = false
      }
    }

    return {
      password,
      loading,
      error,
      handleLogin
    }
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.login-card {
  background: white;
  padding: 40px;
  border-radius: 8px;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
  width: 100%;
  max-width: 400px;
}

h1 {
  margin: 0 0 10px 0;
  color: #333;
  text-align: center;
  font-size: 28px;
}

.subtitle {
  text-align: center;
  color: #666;
  margin-bottom: 30px;
  font-size: 16px;
}

.form-group {
  margin-bottom: 20px;
}

label {
  display: block;
  margin-bottom: 8px;
  color: #555;
  font-weight: 500;
}

input[type="password"] {
  width: 100%;
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
  transition: border-color 0.2s;
}

input[type="password"]:focus {
  outline: none;
  border-color: #667eea;
}

input[type="password"]:disabled {
  background-color: #f5f5f5;
  cursor: not-allowed;
}

button[type="submit"] {
  width: 100%;
  padding: 12px;
  font-size: 16px;
  font-weight: 600;
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
