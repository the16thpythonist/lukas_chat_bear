<template>
  <div class="dashboard">
    <nav class="navbar">
      <div class="navbar-brand">
        <h1>🐻 Lukas Dashboard</h1>
      </div>
      <div class="navbar-menu">
        <router-link to="/activity" class="nav-link">Activity Log</router-link>
        <router-link to="/images" class="nav-link">Images</router-link>
        <router-link to="/events" class="nav-link">Events</router-link>
        <router-link to="/controls" class="nav-link">Controls</router-link>
      </div>
      <div class="navbar-actions">
        <button @click="handleLogout" class="btn btn-secondary">Logout</button>
      </div>
    </nav>

    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<script>
import { useRouter } from 'vue-router'
import { logout } from '../services/auth'

export default {
  name: 'Dashboard',
  setup() {
    const router = useRouter()

    const handleLogout = async () => {
      await logout()
      router.push('/login')
    }

    return {
      handleLogout
    }
  }
}
</script>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.navbar {
  background: white;
  border-bottom: 1px solid #e0e0e0;
  padding: 0 20px;
  display: flex;
  align-items: center;
  height: 60px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.navbar-brand h1 {
  margin: 0;
  font-size: 20px;
  color: #333;
}

.navbar-menu {
  display: flex;
  gap: 20px;
  margin-left: 40px;
  flex: 1;
}

.nav-link {
  text-decoration: none;
  color: #666;
  padding: 8px 16px;
  border-radius: 4px;
  transition: all 0.2s;
  font-weight: 500;
}

.nav-link:hover {
  background-color: #f5f5f5;
  color: #333;
}

.nav-link.router-link-active {
  background-color: #667eea;
  color: white;
}

.navbar-actions {
  margin-left: auto;
}

.main-content {
  flex: 1;
  padding: 20px;
  background-color: #f5f5f5;
}
</style>
