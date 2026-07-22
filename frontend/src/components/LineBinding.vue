
<template>
  <div class="line-binding-card">
    <h3>綁定排班小幫手 (LINE)</h3>
    <p>綁定後，您可以直接透過 LINE 向小幫手請假、查詢班表，甚至接收颱風假停班通知！</p>
    
    <button v-if="!bindCode" @click="generateCode" class="btn-primary" :disabled="isLoading"
    >
      {{ isLoading ? '產生中...' : '產生 6 位數綁定碼' }}
    </button>

    <div v-else class="binding-instructions"
    >
      <div class="code-display">
        您的專屬綁定碼：<strong>{{ bindCode }}</strong>
      </div>
      <p class="instruction-text">
        請打開電視台的 LINE 官方帳號，輸入並發送：<br/>
        <span class="highlight">綁定 {{ bindCode }}</span>
      </p>
      <p class="warning-text">※ 此驗證碼僅單次有效，請盡快完成綁定。</p>
    </div>

    <div v-if="toast.show" class="fixed bottom-5 left-1/2 transform -translate-x-1/2 bg-gray-800 text-white px-4 py-2 rounded shadow-lg z-50">
      {{ toast.message }}
    </div>
  </div>
</template>


<script setup>
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import api from '@/api'

const authStore = useAuthStore()

const bindCode = ref(null)
const isLoading = ref(false)


const toast = ref({ show: false, message: '' })
const showToast = (msg) => { toast.value.message = msg; toast.value.show = true; setTimeout(() => { toast.value.show = false }, 3500) }



const generateCode = async () => {
    const currentUserId = authStore.userId;

    if (!currentUserId || currentUserId === 'undefined' || currentUserId === 'null') {
      showToast('無法取得帳號身分，請重新登入！')
      return
    }
    
    isLoading.value = true
    try {
        const res = await api.post(`/users/${currentUserId}/generate_bind_code`)
        bindCode.value = res.data.bind_code
        showToast('綁定碼已產生！')
    } catch (error) {
        showToast(`發生錯誤：${error.response?.data?.detail || '請稍後再試'}`)
    } finally {
        isLoading.value = false
    }
}
</script>


<style scoped>
.line-binding-card {
  padding: 20px;
  border: 1px solid #4CAF50;
  border-radius: 8px;
  background-color: #f9fff9;
  max-width: 400px;
  text-align: center;
}
.btn-primary { background-color: #00B900; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; font-size: 16px; }
.btn-primary:disabled { background-color: #ccc; cursor: not-allowed; }
.code-display { font-size: 1.2rem; margin: 15px 0; padding: 10px; background: #eee; border-radius: 4px; }
.highlight { color: #00B900; font-weight: bold; font-size: 1.1rem; }
.warning-text { font-size: 0.85rem; color: #666; }
</style>