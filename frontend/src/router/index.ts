import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '../views/LoginView.vue'
import AdminView from '../views/AdminView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: LoginView,
      meta: { requiresAuth: false }
    },
    {
      path: '/admin',
      component: AdminView,
      meta: { requiresAuth: true },
      children: [
        {
          path: 'agent',
          name: 'AdminAgent',
          component: () => import('@/components/admin/AgentTab.vue')
        },
        {
          path: 'calendar',
          name: 'AdminCalendar',
          component: () => import('@/components/admin/CalendarTab.vue')
        },
        {
          path: 'matrix',
          name: 'AdminMatrix',
          component: () => import('@/components/admin/MatrixTab.vue')
        },
        {
          path: 'schedule',
          name: 'AdminSchedule',
          component: () => import('@/components/admin/ScheduleTab.vue')
        },
        {
          path: 'organization',
          name: 'AdminOrganization',
          component: () => import('@/components/admin/OrganizationTab.vue')
        },
        {
          path: 'programs',
          name: 'AdminPrograms',
          component: () => import('@/components/admin/ProgramsTab.vue')
        },
        {
          path: 'accounts',
          name: 'AdminAccounts',
          component: () => import('@/components/admin/AccountsTab.vue')
        },
        {
          path: 'system_settings',
          name: 'AdminSystemSettings',
          component: () => import('@/components/admin/SystemSettingsTab.vue')
        },
        {
          path: 'daily-detail',
          name: 'AdminDailyDetail',
          component: () => import('@/components/admin/DailyDetailTab.vue')
        },
        {
          path: 'settlement',
          name: 'AdminSettlement',
          component: () => import('@/components/admin/TimeReport.vue')
        }
      ]
    },
    {
      path: '/',
      redirect: '/admin',
      meta: { requiresAuth: true }
    },
    {
      path: '/line-binding',
      name: 'LineBinding',
      component: () => import('@/views/LineBindingView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/admin',
      meta: { requiresAuth: true }
    }
  ]
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  const requiresAuth = to.meta.requiresAuth

  if (requiresAuth && !token) {
    next({ name: 'login' })
  } else if (to.name === 'login' && token) {
    next({ path: '/admin' })
  } else {
    next()
  }
})

export default router
