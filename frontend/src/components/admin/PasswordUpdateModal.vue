<template>
  <div v-if="show" class="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 backdrop-blur-sm animate-fade-in" @click.self="closeModal">
    <div class="bg-white rounded-2xl shadow-xl w-full max-w-md p-6 border border-gray-100">
      <h3 class="text-lg font-bold text-gray-900 mb-4">修改帳號密碼</h3>
      
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-gray-700">舊密碼</label>
          <input 
            v-model="passwordForm.old_password" 
            type="password" 
            class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
            placeholder="請輸入目前密碼"
          />
        </div>
        
        <div>
          <label class="block text-sm font-medium text-gray-700">新密碼</label>
          <input 
            v-model="passwordForm.new_password" 
            type="password" 
            class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
            placeholder="至少 8 碼"
          />
        </div>
        
        <div>
          <label class="block text-sm font-medium text-gray-700">確認新密碼</label>
          <input 
            v-model="passwordForm.confirm_password" 
            type="password" 
            class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
            placeholder="請再次輸入新密碼"
          />
        </div>

        <div v-if="passwordError" class="text-sm text-red-600 bg-red-50 p-3 rounded-lg">
          {{ passwordError }}
        </div>
      </div>

      <div class="mt-6 flex justify-end space-x-3">
        <button @click="closeModal" :disabled="isUpdatingPassword" class="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50">
          取消
        </button>
        <button @click="executePasswordUpdate" :disabled="isUpdatingPassword || !passwordForm.old_password || !passwordForm.new_password || !passwordForm.confirm_password" class="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 flex items-center">
          <svg v-if="isUpdatingPassword" class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
          確認修改
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import api from '@/api'
import { useToast } from 'vue-toastification'

const props = defineProps({ show: Boolean })
const emit = defineEmits(['update:show'])
const toast = useToast()

const isUpdatingPassword = ref(false)
const passwordError = ref('')
const passwordForm = ref({ old_password: '', new_password: '', confirm_password: '' })

const closeModal = () => {
  passwordForm.value = { old_password: '', new_password: '', confirm_password: '' }
  passwordError.value = ''
  emit('update:show', false)
}

const executePasswordUpdate = async () => {
  passwordError.value = ''
  if (passwordForm.value.new_password.length < 8) return passwordError.value = '新密碼長度至少需 8 碼。'
  if (passwordForm.value.new_password !== passwordForm.value.confirm_password) return passwordError.value = '新密碼與確認密碼不一致。'
  
  try {
    isUpdatingPassword.value = true
    await api.put('/users/me/password', passwordForm.value)
    closeModal()
    toast.success('密碼修改成功！')
  } catch (error) {
    passwordError.value = error.response?.data?.detail || '密碼修改失敗，請檢查舊密碼是否正確。'
  } finally {
    isUpdatingPassword.value = false
  }
}
</script>