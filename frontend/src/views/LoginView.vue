<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-50">
    
    <div 
      v-if="toast.show" 
      class="fixed top-8 left-1/2 transform -translate-x-1/2 z-50 bg-gray-900 text-white px-6 py-3 rounded-full shadow-2xl transition-all flex items-center space-x-3"
      style="animation: dropDown 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);"
    >
      <span class="font-medium tracking-wide">{{ toast.message }}</span>
    </div>

    <div class="bg-white p-10 rounded-2xl shadow-xl border border-gray-100 w-full max-w-md">
      <h1 class="text-3xl font-bold text-gray-800 mb-2 text-center">排班系統</h1>
      <p class="text-gray-500 text-center mb-8">請輸入您的帳號與密碼</p>

      <div class="space-y-6">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">帳號</label>
          <input 
            v-model="username" 
            @keydown.enter="login($event)" 
            type="text" 
            class="w-full border border-gray-300 rounded-lg p-3 outline-none focus:ring-2 focus:ring-blue-500 transition-shadow" 
            placeholder="例如：admin" 
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">密碼</label>
          <input 
            v-model="password" 
            @keydown.enter="login($event)" 
            type="password" 
            class="w-full border border-gray-300 rounded-lg p-3 outline-none focus:ring-2 focus:ring-blue-500 transition-shadow" 
            placeholder="請輸入密碼" 
          />
        </div>
        <button 
          @click="login" 
          class="w-full bg-blue-600 text-white py-3 rounded-lg hover:bg-blue-700 font-bold transition-colors shadow-sm"
        >
          登入系統
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/api'
import { useAuthStore } from '@/stores/auth'



const router = useRouter()
const authStore = useAuthStore()
const username = ref('')
const password = ref('')



const toast = ref({ show: false, message: '' })
const showToast = (msg) => {
  toast.value.message = msg
  toast.value.show = true
  setTimeout(() => { toast.value.show = false }, 3500)
}



const login = async (event) => {
  if (event && (event.isComposing || event.keyCode === 229)) {
    return;
  }

  if (!username.value || !password.value) {
    return showToast("請輸入完整的帳號與密碼")
  }
  
  try {
    const res = await api.post('/auth/login', {
      username: username.value,
      password: password.value
    })
    
    console.log("後端回傳的登入資料:", res.data);
    
    authStore.setToken(
      res.data.access_token, 
      res.data.role, 
      res.data.user_id,
      res.data.staff_id
    )
    showToast("登入成功！正在導向...")
    
    setTimeout(() => { router.replace('/') }, 500)
    
  } catch (error) {
    showToast(error.response?.data?.detail || "登入失敗，後端伺服器無回應")
  }
}
</script>

<style scoped>
@keyframes dropDown { 
  from { top: -20px; opacity: 0; } 
  to { top: 32px; opacity: 1; } 
}
</style>
