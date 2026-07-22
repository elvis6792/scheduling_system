<template>
  <div class="bg-white p-6 rounded-xl shadow-sm border min-h-[600px] flex flex-col animate-fade-in mb-6">
    <div class="flex justify-between items-center mb-4">
      <h2 class="text-xl font-bold text-gray-800" @click="goToToday">
        <span v-if="userRole === 'staff'">我的排班與休假</span>
        <span v-else>全公司總表與排班</span>
      </h2>
      <div class="flex space-x-4 items-center">
        <button @click="prevMonth" class="px-3 py-1 bg-gray-100 hover:bg-gray-200 rounded-lg font-bold transition-colors">上一月</button>
        <span class="font-bold text-lg text-gray-700">{{ currentYear }} 年 {{ currentMonth }} 月</span>
        <button @click="nextMonth" class="px-3 py-1 bg-gray-100 hover:bg-gray-200 rounded-lg font-bold transition-colors">下一月</button>
      </div>
    </div>

    <div class="mb-6 animate-fade-in" v-if="userRole === 'staff'">
      <div class="bg-gradient-to-r from-green-50 to-teal-50 p-6 rounded-xl border border-green-200 flex items-center justify-between">
        <div>
          <h3 class="font-bold text-green-800 text-lg">連接您的 LINE 帳號</h3>
          <p class="text-sm text-green-700 mt-1">開啟即時班表通知、線上請假與 AI 助理對話功能。</p>
        </div>
        <router-link to="/line-binding" class="bg-green-600 text-white font-bold py-2 px-5 rounded-lg hover:bg-green-700 transition-colors shadow-md flex items-center">
          前往設定
        </router-link>
      </div>
    </div>

    <div class="overflow-x-auto custom-scrollbar border border-gray-200 rounded-lg shadow-inner flex-1">
      <table class="w-full text-left border-collapse min-w-max text-sm relative">
        <thead class="sticky top-0 z-20 bg-gray-100 shadow-sm">
          <tr>
            <th class="p-3 font-bold text-gray-600 border-b border-r sticky left-0 bg-gray-100 z-30 w-32">部門 / 人員</th>
            <th v-for="day in matrixDays" :key="day.dateStr"
                :class="['p-2 text-center border-b border-r min-w-[80px]', day.isWeekend ? 'bg-red-50 text-red-600' : 'text-gray-600']">
              <div class="font-bold text-lg">{{ day.day }}</div>
              <div class="text-xs font-bold">{{ day.weekdayStr }}</div>
            </th>
          </tr>
        </thead>
        <tbody>
          <template v-for="dept in departmentsToDisplay" :key="dept.id">
            <tr v-if="getStaffByDept(dept.id).length > 0" class="bg-gray-50 border-b">
              <td :colspan="matrixDays.length + 1" class="p-2 font-bold text-gray-700 bg-gray-200 sticky left-0 z-10 text-left shadow-sm">
                {{ dept.name }}
              </td>
            </tr>
            <tr v-for="staff in getStaffByDept(dept.id)" :key="staff.id" class="border-b hover:bg-blue-50 transition-colors">
              <td class="p-3 font-medium text-gray-800 border-r sticky left-0 bg-white z-10 shadow-[2px_0_5px_-2px_rgba(0,0,0,0.1)]">
                {{ staff.name }}
              </td>
              <td v-for="day in matrixDays" :key="day.dateStr"
                  @click="$emit('cell-click', staff.id, day.dateStr, staff.name, dept.id)"
                  :class="[
                    'p-1 border-r text-center relative group min-h-[3rem] transition-colors align-top',
                    day.isWeekend ? 'bg-red-50/30' : '',
                    userRole === 'staff' && String(staff.id) !== String(currentStaffId) ? 'cursor-not-allowed hover:bg-gray-100 opacity-60 grayscale' : 'cursor-pointer hover:bg-orange-100'
                  ]">

                <!-- 顯示當日上班時數上限 (含臨時調整) -->
                <div class="mb-1 flex justify-center">
                  <span :class="[
                    'text-[9px] px-1 rounded font-bold border',
                    workHoursMatrixMap[staff.id] && workHoursMatrixMap[staff.id][day.dateStr]
                      ? 'bg-blue-600 text-white border-blue-700 shadow-sm'
                      : 'bg-gray-100 text-gray-500 border-gray-200'
                  ]" :title="workHoursMatrixMap[staff.id] && workHoursMatrixMap[staff.id][day.dateStr] ? '臨時調整時數' : '標準工時'">
                    {{ getDailyLimit(staff, day.dateStr) }}h
                  </span>
                </div>

                <div class="space-y-1 custom-scrollbar">
                  <template v-if="shiftMatrixMap[staff.id] && shiftMatrixMap[staff.id][day.dateStr]">
                    <div v-for="shift in shiftMatrixMap[staff.id][day.dateStr]" :key="shift.id"
                          :class="[
                            'text-[10px] font-bold p-1 rounded shadow-sm text-white whitespace-normal',
                            shift.notes && shift.notes.includes('颱風停班') ? 'bg-red-500 ring-2 ring-red-300 ring-offset-1' : ''
                          ]"
                          :style="shift.notes && shift.notes.includes('颱風停班') ? {} : { backgroundColor: getProgramColor(shift.program_id) }">
                      {{ getProgramName(shift.program_id) }}
                    </div>
                  </template>
                  <div v-if="leaveMatrixMap[staff.id] && leaveMatrixMap[staff.id][day.dateStr]"
                      class="bg-pink-100 text-pink-800 text-[10px] font-bold p-1 rounded border border-pink-200 shadow-sm whitespace-normal">
                    {{ leaveMatrixMap[staff.id][day.dateStr].leave_type }} {{ leaveMatrixMap[staff.id][day.dateStr].hours }}hr
                  </div>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import { useScheduleStore } from '@/stores/schedule'
import { useCalendar } from '@/composables/useCalendar'

// 1. 取得身分驗證資訊
const authStore = useAuthStore()
const { role: userRole, staffId: currentStaffId } = storeToRefs(authStore)

// 2. 從 Pinia 拿回全域資料
const scheduleStore = useScheduleStore()
const {
  departments, staffList, programs, leaves, matrixDays, shiftMatrixMap, leaveMatrixMap, workHoursMatrixMap,
  currentYear, currentMonth
} = storeToRefs(scheduleStore)

const today = new Date()

// 取得當日工時上限 (考慮覆寫)
const getDailyLimit = (staff, dateStr) => {
  // 優先看是否有臨時調整 (覆寫)
  if (workHoursMatrixMap.value[staff.id] && workHoursMatrixMap.value[staff.id][dateStr] !== undefined) {
    return workHoursMatrixMap.value[staff.id][dateStr].toFixed(1);
  }
  // 否則回傳員工預設工時
  return (staff.daily_work_hours || 8.0).toFixed(1);
}

// 5. 畫面渲染輔助邏輯 (從原本的 AdminView 搬過來)
const departmentsToDisplay = computed(() => {
  if (userRole.value === 'staff') {
    if (!currentStaffId.value) return []
    const self = staffList.value.find(s => String(s.id) === String(currentStaffId.value))
    if (!self) return []
    const selfDept = departments.value.find(d => d.id === self.department_id)
    return selfDept ? [selfDept] : [{ id: self.department_id, name: '我的部門' }]
  }
  return departments.value
})

const getStaffByDept = (deptId) => {
  return staffList.value.filter(s => s.department_id === deptId)
}

const getProgramColor = (progId) => {
  const p = programs.value.find(x => x.id === progId)
  return p ? (p.color || '#6366f1') : '#6366f1'
}

const getProgramName = (progId) => {
  const p = programs.value.find(x => x.id === progId)
  return p ? p.name : '未指定節目'
}

// 6. 時間切換邏輯
const goToToday = () => { currentYear.value = today.getFullYear(); currentMonth.value = today.getMonth() + 1 }

const prevMonth = () => {
  if (currentMonth.value === 1) { currentMonth.value = 12; currentYear.value-- } else { currentMonth.value-- }
}
const nextMonth = () => {
  if (currentMonth.value === 12) { currentMonth.value = 1; currentYear.value++ } else { currentMonth.value++ }
}

// 向外發送單元格點擊事件 (交給 AdminLayout 的彈窗處理)
defineEmits(['cell-click'])
</script>
