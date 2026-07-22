<template>
  <div class="grid grid-cols-1 md:grid-cols-3 gap-8 animate-fade-in">
    <!-- 左側：新增節目表單 -->
    <div class="md:col-span-1 bg-white p-6 rounded-xl shadow-sm border">
      <h3 class="text-lg font-bold text-gray-800 mb-4 border-b pb-2">新增節目</h3>
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">節目名稱</label>
          <input v-model="newProg.name" @keydown.enter="addProgram($event)" type="text" class="w-full border border-gray-300 rounded-lg p-2 outline-none focus:ring-2 focus:ring-blue-500" placeholder="例如：大愛劇場">
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">內容描述 (選填)</label>
          <textarea v-model="newProg.content" rows="3" class="w-full border border-gray-300 rounded-lg p-2 outline-none focus:ring-2 focus:ring-blue-500" placeholder="節目的簡要說明"></textarea>
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">預估時數 (小時)</label>
          <input v-model.number="newProg.estimated_hours" type="number" step="0.5" class="w-full border border-gray-300 rounded-lg p-2 outline-none focus:ring-2 focus:ring-blue-500">
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">代表色</label>
          <div class="flex space-x-2">
            <button v-for="color in presetColors" :key="color" @click="newProg.color = color" :style="{ backgroundColor: color }" class="w-8 h-8 rounded-full transition-transform transform hover:scale-110" :class="{'ring-2 ring-offset-2 ring-black': newProg.color === color}"></button>
          </div>
        </div>
        <button @click="addProgram" class="w-full bg-blue-600 text-white py-2.5 rounded-lg hover:bg-blue-700 font-bold transition-colors">新增節目</button>
      </div>
    </div>

    <!-- 右側：節目列表 -->
    <div class="md:col-span-2 bg-white p-6 rounded-xl shadow-sm border">
      <h3 class="text-lg font-bold text-gray-800 mb-4 border-b pb-2">節目清單</h3>
      <div class="overflow-y-auto max-h-[500px] custom-scrollbar pr-2">
        <div v-if="programs.length === 0" class="text-center text-gray-400 py-8">
          尚未建立任何節目
        </div>
        <ul v-else class="space-y-3">
          <li v-for="prog in programs" :key="prog.id" class="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-200 hover:shadow-md transition-shadow">
            <div class="flex items-center">
              <span class="w-5 h-5 rounded-full mr-4" :style="{ backgroundColor: prog.color }"></span>
              <div>
                <p class="font-bold text-gray-800">{{ prog.name }}</p>
                <p class="text-xs text-gray-500">預估時數: {{ prog.estimated_hours }}h</p>
              </div>
            </div>
            <button @click="deleteProgram(prog.id)" class="text-gray-400 hover:text-red-500 font-bold text-xl transition-colors">&times;</button>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useScheduleStore } from '@/stores/schedule'
import { useToast } from 'vue-toastification'
import api from '@/api'

const toast = useToast()
const scheduleStore = useScheduleStore()
const { programs } = storeToRefs(scheduleStore)

const props = defineProps({
  showConfirm: Function
})

// 1. 把原本在 AdminView 的變數搬過來
const presetColors = ['#ef4444', '#f97316', '#f59e0b', '#10b981', '#06b6d4', '#3b82f6', '#6366f1', '#8b5cf6', '#ec4899', '#64748b']
const newProg = ref({ name: '', content: '', estimated_hours: 4.0, color: '#6366f1' })

// 2. 把原本在 AdminView 的業務邏輯搬過來
const addProgram = async (event) => {
  if (event && event.isComposing) return
  if (!newProg.value.name) return toast.warning("請輸入節目名稱！")
  
  try {
    await api.post('/programs', newProg.value)
    toast.success("節目建檔成功")
    newProg.value = { name: '', content: '', estimated_hours: 4.0, color: '#6366f1' }
    
    // 直接呼叫 Store 的方法重新抓資料
    await scheduleStore.fetchPrograms()
  } catch (e) {
    toast.error("建檔失敗：" + (e.response?.data?.detail || e.message))
  }
}

const deleteProgram = async (id) => {
  if (props.showConfirm) {
    const ok = await props.showConfirm('確定刪除此節目嗎？', 'cancel')
    if (!ok) return
  } else {
    if (!confirm('確定刪除此節目嗎？')) return
  }
  try {
    await api.delete(`/programs/${id}`)
    toast.success("刪除成功")
    await scheduleStore.fetchPrograms()
  } catch (e) {
    toast.error("刪除失敗")
  }
}
</script>