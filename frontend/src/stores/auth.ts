import { defineStore } from 'pinia'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || null,
    role: localStorage.getItem('role') || null,
    userId: localStorage.getItem('userId') || null,
    staffId: localStorage.getItem('staffId') || null,
  }),
  actions: {
    setToken(token: string, role: string, userId?: string | number, staffId?: string | number | null) {
      this.token = token
      this.role = role
      this.userId = userId ? String(userId) : null
      this.staffId = staffId ? String(staffId) : null
      
      localStorage.setItem('token', token)
      localStorage.setItem('role', role)
      if (this.userId) localStorage.setItem('userId', this.userId)
      if (this.staffId) localStorage.setItem('staffId', this.staffId)
    },
    
    clearToken() {
      this.token = null
      this.role = null
      this.userId = null
      this.staffId = null
      
      localStorage.removeItem('token')
      localStorage.removeItem('role')
      localStorage.removeItem('userId')
      localStorage.removeItem('staffId')
    },
  },
})