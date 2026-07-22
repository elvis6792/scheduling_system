<template>
  <div class="grid grid-cols-1 md:grid-cols-3 gap-8 animate-fade-in">
    <!-- 左側：排班條件 -->
    <div class="md:col-span-1 bg-white p-6 rounded-xl shadow-sm border">
      <h3 class="text-lg font-bold text-gray-800 mb-4 border-b pb-2">1. 設定排班條件</h3>
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">選擇節目</label>
          <select v-model="scheduleQuery.program_id" class="w-full border border-gray-300 rounded-lg p-2 outline-none focus:ring-2 focus:ring-blue-500 bg-white" data-testid="program-select">
            <option disabled value="">請選擇一個節目</option>
            <option v-for="prog in programs" :key="prog.id" :value="prog.id">{{ prog.name }}</option>
          </select>
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">選擇部門</label>
          <select v-model="scheduleQuery.department_id" class="w-full border border-gray-300 rounded-lg p-2 outline-none focus:ring-2 focus:ring-blue-500 bg-white" data-testid="department-select">
            <option disabled value="">請選擇部門</option>
            <option v-for="dept in departments" :key="dept.id" :value="dept.id">{{ dept.name }}</option>
          </select>
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">排班日期</label>
          <input v-model="scheduleQuery.date" type="date" class="w-full border border-gray-300 rounded-lg p-2 outline-none focus:ring-2 focus:ring-blue-500" data-testid="date-input">
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">排班時數 (自動帶入)</label>
          <input v-model.number="scheduleQuery.duration" type="number" step="0.5" class="w-full border border-gray-300 rounded-lg p-2 outline-none focus:ring-2 focus:ring-blue-500 bg-gray-100" readonly data-testid="duration-input">
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">備註 (選填)</label>
          <textarea v-model="scheduleQuery.notes" rows="2" class="w-full border border-gray-300 rounded-lg p-2 outline-none focus:ring-2 focus:ring-blue-500" placeholder="例如：特殊需求" data-testid="notes-input"></textarea>
        </div>
        <button @click="searchAvailableStaff" class="w-full bg-blue-600 text-white py-2.5 rounded-lg hover:bg-blue-700 font-bold transition-colors" data-testid="search-staff-button">
          2. 查詢可排班人力
        </button>
      </div>
    </div>

    <!-- 右側：可用人力列表 -->
    <div class="md:col-span-2 bg-white p-6 rounded-xl shadow-sm border" data-testid="available-staff-list">
      <h3 class="text-lg font-bold text-gray-800 mb-4 border-b pb-2">3. 指派人力</h3>
      <div class="overflow-y-auto max-h-[500px] custom-scrollbar pr-2">
        <div v-if="availableStaff.length === 0" class="text-center text-gray-400 py-8">
          請先查詢或此條件下無可用人力
        </div>
        <ul v-else class="space-y-3">
          <li v-for="staff in availableStaff" :key="staff.id" class="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-200 hover:shadow-sm transition-shadow">
            <div>
              <p class="font-bold text-gray-800">{{ staff.name }}</p>
              <p class="text-xs text-gray-500">尚可安排時數: {{ staff.remaining_available_hours }} hr</p>
            </div>
            <button @click="assignShift(staff.id)" class="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 font-bold transition-colors whitespace-nowrap" :data-testid="`assign-button-${staff.id}`">
              指派此人
            </button>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useScheduleStore } from '@/stores/schedule'
import { useToast } from 'vue-toastification'
import api from '@/api'

const toast = useToast()
const scheduleStore = useScheduleStore()

// 1. 從 Pinia 拿回下拉選單需要的資料
const { programs, departments } = storeToRefs(scheduleStore)

// 2. 獨立管理專屬的表單狀態
const availableStaff = ref([])
const scheduleQuery = ref({
  program_id: '',
  episode: '',
  department_id: '',
  date: '',
  duration: 0,
  notes: ''
})

// 連動節目時數 (當選擇不同節目時，自動帶入預估工時)
watch(() => scheduleQuery.value.program_id, (newProgId) => {
  if (newProgId) {
    const program = programs.value.find(p => p.id === newProgId)
    if (program) {
      scheduleQuery.value.duration = program.estimated_hours
    }
  }
})

// 3. 搜尋可用名單邏輯
const searchAvailableStaff = async () => {
  if (!scheduleQuery.value.date || !scheduleQuery.value.department_id || !scheduleQuery.value.program_id) {
    toast.warning("請先選擇節目、部門與日期")
    return
  }
  try {
    const res = await api.get('/staff/available', {
      params: {
        date: scheduleQuery.value.date,
        department_id: scheduleQuery.value.department_id
      }
    })
    availableStaff.value = res.data
    if (res.data.length === 0) {
      toast.warning("該部門於此日期已無人力！")
    }
  } catch (e) {
    toast.error("查詢失敗")
  }
}

// 4. 指派排班邏輯
const assignShift = async (staffId) => {
  const payload = {
    staff_id: staffId,
    ...scheduleQuery.value
  }
  try {
    await api.post('/shifts', payload)
    toast.success("排班成功！")
    
    // 清空部分表單
    scheduleQuery.value.program_id = ''
    scheduleQuery.value.notes = ''
    availableStaff.value = []
    
    // 呼叫 Store 重新撈取資料，確保月曆和矩陣表同步更新
    await scheduleStore.fetchAllData('admin')
  } catch (e) {
    toast.error("排班失敗：" + (e.response?.data?.detail || e.message))
  }
}
</script>