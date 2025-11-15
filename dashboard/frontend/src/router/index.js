import { createRouter, createWebHistory } from 'vue-router'
import { checkSession } from '../services/auth'

// Import actual views
import Login from '../views/Login.vue'
import Dashboard from '../views/Dashboard.vue'
import ActivityLog from '../views/ActivityLog.vue'
import ImagesGallery from '../views/ImagesGallery.vue'
import ScheduledEvents from '../views/ScheduledEvents.vue'
import ManualControls from '../views/ManualControls.vue'

const routes = [
  {
    path: '/',
    name: 'Home',
    redirect: '/activity'
  },
  {
    path: '/login',
    name: 'Login',
    component: Login
  },
  {
    path: '/',
    component: Dashboard,
    meta: { requiresAuth: true },
    children: [
      {
        path: 'activity',
        name: 'Activity',
        component: ActivityLog
      },
      {
        path: 'images',
        name: 'Images',
        component: ImagesGallery
      },
      {
        path: 'events',
        name: 'Events',
        component: ScheduledEvents
      },
      {
        path: 'controls',
        name: 'Controls',
        component: ManualControls
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Navigation guard for authentication
router.beforeEach(async (to, from, next) => {
  // Allow access to login page
  if (to.path === '/login') {
    return next()
  }

  // Check if route requires authentication
  if (to.meta.requiresAuth) {
    const session = await checkSession()
    if (!session.authenticated) {
      return next('/login')
    }
  }

  next()
})

export default router
