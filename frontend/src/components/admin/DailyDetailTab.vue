<template>
  <div class="animate-fade-in mb-6">
    <div class="mb-4 flex items-center justify-between">
      <button @click="$emit('back-to-calendar')" class="flex items-center text-gray-600 hover:text-blue-600 transition-colors font-medium" data-testid="back-to-calendar-button">
        <svg class="w-5 h-5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"></path>
        </svg>
        返回月曆
      </button>
      <button @click="jumpToSchedule(selectedDailyDate)" class="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 font-medium shadow-sm transition-colors" data-testid="jump-to-schedule-button">+ 新增排班</button>
    </div>
    <div class="bg-white p-8 rounded-xl shadow-sm border border-gray-100 min-h-[500px]">
      <div class="flex flex-col md:flex-row justify-between items-start md:items-end mb-8 border-b pb-4 gap-4">
        <div>
          <h2 class="text-3xl font-bold text-gray-800 mb-2">{{ selectedDailyDate }} 排班總覽</h2>
          <p class="text-gray-500">此處顯示該日期的所有人員排班資訊</p>
        </div>
        <div class="flex items-center bg-gray-50 p-2 rounded-lg border border-gray-200">
          <label class="text-sm font-medium text-gray-600 mr-2 whitespace-nowrap">篩選部門：</label>
          <select
            v-model="dailyDetailDeptId"
            class="border-none bg-transparent outline-none text-sm font-bold text-gray-800 w-full cursor-pointer"
            data-testid="daily-detail-dept-select"
          >
            <option value="">全公司 (顯示所有部門)</option>
            <option v-for="d in departments" :key="d.id" :value="d.id">{{ d.name }}</option>
          </select>
        </div>
      </div>
      <div v-if="dailyShiftsList.length === 0" class="flex flex-col items-center justify-center h-48 text-gray-400 bg-gray-50 rounded-xl border border-dashed border-gray-200" data-testid="no-shifts-message">
        <p>本日目前尚無符合條件的排班紀錄</p>
      </div>
      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div v-for="shift in dailyShiftsList" :key="shift.id" class="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow overflow-hidden">
          <div class="bg-gray-50 px-4 py-3 border-b border-gray-200 flex justify-between items-center">
            <div>
              <span class="font-bold text-gray-800">{{ getStaffName(shift.staff_id) }}</span>
              <span class="ml-2 text-xs bg-gray-200 text-gray-700 px-2 py-1 rounded-full">{{ getDeptName(shift.department_id) }}</span>
            </div>
            <div class="flex items-center space-x-2">
              <button @click="$emit('open-shift-edit-modal', shift)" class="text-blue-600 hover:text-blue-800 text-sm font-bold px-2 py-1 hover:bg-blue-50 rounded transition-colors" :data-testid="`edit-shift-${shift.id}`">修改排班</button>
              <button @click="$emit('delete-shift', shift.id)" class="text-red-500 hover:text-red-700 text-sm font-medium px-2 py-1 hover:bg-red-50 rounded transition-colors" :data-testid="`delete-shift-${shift.id}`">取消排班</button>
            </div>
          </div>
          <div class="p-4 space-y-3">
            <div class="flex items-start">
              <span class="text-gray-400 mr-2 w-12 text-sm">節目：</span>
              <span class="font-medium text-gray-800">{{ getProgramName(shift.program_id) }}</span>
            </div>
            <div class="flex items-start">
              <span class="text-gray-400 mr-2 w-12 text-sm">時段：</span>
              <span class="text-gray-700">{{ shift.start_time.substring(0,5) }} ~ {{ shift.end_time.substring(0,5) }}</span>
            </div>
            <div class="flex items-start">
              <span class="text-gray-400 mr-2 w-12 text-sm">備註：</span>
              <span class="text-gray-600 text-sm italic">{{ shift.notes || '無特別需求' }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useScheduleStore } from '@/stores/schedule'

const router = useRouter()
const route = useRoute()
const scheduleStore = useScheduleStore()
const { departments, staffList, programs, monthlyShifts } = storeToRefs(scheduleStore)

const selectedDailyDate = computed(() => route.query.date || '')
const dailyDetailDeptId = ref('')

const dailyShiftsList = computed(() => {
  let shifts = monthlyShifts.value.filter(shift => shift.date === selectedDailyDate.value)
  if (dailyDetailDeptId.value) {
    shifts = shifts.filter(s => String(s.department_id) === String(dailyDetailDeptId.value))
  }
  return shifts
})

const getDeptName = (id) => departments.value.find(d => d.id === id)?.name || '未知'
const getStaffName = (id) => staffList.value.find(s => s.id === id)?.name || '未知'
const getProgramName = (id) => programs.value.find(p => p.id === id)?.name || '未知節目'

const jumpToSchedule = (dateStr) => {
  // 準備跳轉到手動排班頁面 (如果上了 Router)
  router.push({ path: '/admin/schedule', query: { date: dateStr } })
}

// 刪除與修改事件仍然可以 emit 給外層共用彈窗，或者你也可以把 API 寫在這裡
defineEmits(['back-to-calendar', 'open-shift-edit-modal', 'delete-shift'])
</script>
