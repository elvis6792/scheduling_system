<template>
  <div class="grid grid-cols-1 md:grid-cols-2 gap-8 animate-fade-in">
    <!-- 左側：排班開放日期設定 -->
    <div class="bg-white p-6 rounded-xl shadow-sm border">
      <h3 class="text-lg font-bold text-gray-800 mb-4 border-b pb-2">排班開放日期設定</h3>
      <div class="space-y-4">
        <div class="p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <p class="text-sm font-medium text-blue-800">{{ currentWindowDisplay }}</p>
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">快速設定新的開放截止日</label>
          <input v-model="quickSetDate" type="date" class="w-full border border-gray-300 rounded-lg p-2 outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <button @click="applyQuickSetWindow" :disabled="isSettingWindow" class="w-full bg-blue-600 text-white py-2.5 rounded-lg hover:bg-blue-700 font-bold transition-colors disabled:bg-blue-300">
          {{ isSettingWindow ? '設定中...' : '確認並開放' }}
        </button>
      </div>
    </div>

    <!-- 右側：LINE Bot 串接設定 -->
    <div class="bg-white p-6 rounded-xl shadow-sm border">
      <h3 class="text-lg font-bold text-gray-800 mb-4 border-b pb-2">LINE Bot 串接設定</h3>
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">LINE Channel Access Token</label>
          <input v-model="lineToken" type="text" class="w-full border border-gray-300 rounded-lg p-2 outline-none focus:ring-2 focus:ring-teal-500" placeholder="貼上從 LINE Developer 取得的權杖" />
          <p class="text-xs text-gray-500 mt-1">此權杖將被安全地儲存在後端，用於發送班表通知。</p>
        </div>
        <button @click="saveLineToken" :disabled="isSavingLineToken" class="w-full bg-teal-600 text-white py-2.5 rounded-lg hover:bg-teal-700 font-bold transition-colors disabled:bg-teal-300">
          {{ isSavingLineToken ? '儲存中...' : '儲存權杖' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '@/api'
import { useToast } from 'vue-toastification'

const toast = useToast()
const currentWindowDisplay = ref('正在讀取設定...')
const quickSetDate = ref('')
const isSettingWindow = ref(false)
const lineToken = ref('')
const isSavingLineToken = ref(false)

const fetchTimeWindows = async () => {
  try {
    const res = await api.get('/time-windows')
    const activeWindow = res.data.find(w => w.is_active)
    currentWindowDisplay.value = activeWindow ? `目前已開放至：${activeWindow.end_date}` : '目前未設定未來的排班開放日期。'
  } catch (e) {
    currentWindowDisplay.value = '讀取設定失敗。'
  }
}

const applyQuickSetWindow = async () => {
  if (!quickSetDate.value) return toast.warning('請先選擇要開放的截止日期！')
  try {
    isSettingWindow.value = true
    const res = await api.post('/time-windows/quick-set', { end_date: quickSetDate.value })
    toast.success(res.data.message || '設定成功')
    await fetchTimeWindows()
  } catch (e) {
    toast.error('設定失敗：' + (e.response?.data?.detail || e.message))
  } finally {
    isSettingWindow.value = false
  }
}

const fetchLineConfig = async () => {
  try {
    const res = await api.get('/config/LINE_CHANNEL_ACCESS_TOKEN')
    if (res.data?.value) lineToken.value = '******** (已設定)'
  } catch (e) {
    console.warn('LINE 設定讀取失敗')
  }
}

const saveLineToken = async () => {
  if (!lineToken.value || lineToken.value.startsWith('********')) return toast.warning('請輸入新的 Token')
  isSavingLineToken.value = true
  try {
    await api.post('/config/LINE_CHANNEL_ACCESS_TOKEN', { value: lineToken.value })
    toast.success('LINE 權杖儲存成功！')
    lineToken.value = '******** (已設定)'
  } catch (e) {
    toast.error('儲存失敗')
  } finally {
    isSavingLineToken.value = false
  }
}

onMounted(() => {
  fetchTimeWindows()
  fetchLineConfig()
})
</script>