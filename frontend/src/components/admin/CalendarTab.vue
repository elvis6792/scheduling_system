<template>
  <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-100 animate-fade-in mb-6">
    <div class="flex flex-col md:flex-row justify-between items-center mb-6 space-y-4 md:shadow-none">
      <h2 class="text-2xl font-bold text-gray-800">{{ currentYear }} 年 {{ currentMonth }} 月</h2>
      <div class="flex items-center space-x-4">
        <div class="flex items-center">
          <label class="text-sm font-medium text-gray-600 mr-2">顯示部門：</label>
          <select 
            v-model="calendarDeptId"
            class="border border-gray-300 rounded-lg p-2 bg-white outline-none text-sm"
          >
            <option value="">全公司 (所有部門)</option>
            <option v-for="d in departments" :key="d.id" :value="d.id">{{ d.name }}</option>
          </select>
        </div>
        <div class="flex space-x-2">
          <button @click="prevMonth" class="px-3 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors font-medium">上一月</button>
          <button @click="goToToday" class="px-3 py-2 bg-blue-50 text-blue-700 rounded-lg hover:bg-blue-100 transition-colors font-medium">本月</button>
          <button @click="nextMonth" class="px-3 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors font-medium">下一月</button>
        </div>
      </div>
    </div>
    <div class="border border-gray-200 rounded-xl overflow-hidden bg-gray-50">
      <div class="grid grid-cols-7 bg-white border-b border-gray-200">
        <div v-for="day in ['週日', '週一', '週二', '週三', '週四', '週五', '週六']" :key="day" class="py-3 text-center text-sm font-semibold text-gray-500">{{ day }}</div>
      </div>
      <div class="grid grid-cols-7 bg-gray-200 gap-px">
        <div v-for="(day, index) in calendarDays" :key="index" @click="day.isCurrentMonth ? openDailyDetail(day.date) : null" :class="['min-h-[120px] bg-white p-2 transition-colors relative group', day.isCurrentMonth ? 'cursor-pointer hover:bg-blue-50' : 'bg-gray-50 opacity-50', day.isToday ? 'bg-yellow-50' : '']">
          <div :class="['text-sm font-bold mb-1', day.isToday ? 'text-blue-600' : 'text-gray-700']">{{ day.dayNumber }}<span v-if="day.isToday" class="ml-1 text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">本日</span></div>
          <div class="space-y-1 max-h-[80px] overflow-y-auto custom-scrollbar pr-1">
            <div v-for="shift in getShiftsForDate(day.date)" :key="shift.id" class="text-xs bg-blue-100 border border-blue-200 text-blue-800 px-1.5 py-1 rounded shadow-sm truncate">
              <span class="font-bold">{{ getStaffName(shift.staff_id) }}</span>: {{ getProgramName(shift.program_id) }}
            </div>
          </div>
          <div v-if="day.isCurrentMonth" class="absolute bottom-1 right-2 opacity-0 group-hover:opacity-100 text-[10px] text-blue-500 font-medium transition-opacity">查看明細</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import { useScheduleStore } from '@/stores/schedule'

const router = useRouter()
const scheduleStore = useScheduleStore()
const authStore = useAuthStore()
const { role: userRole } = storeToRefs(authStore)

// 1. 從 Pinia 拿回全域資料
const {
  departments, staffList, programs, monthlyShifts, calendarDays, calendarDeptId,
  currentYear, currentMonth
} = storeToRefs(scheduleStore)

const today = new Date()

// 當年月改變時，自動重新撈取該月班表 (這裡的 fetchData 會在 AdminView 被呼叫，但我們在這裡也留著以防萬一，或直接讓 AdminView 處理)
// 實際上 AdminView 已經有 watch [currentYear, currentMonth] 了

// 4. 輔助函數：取得名稱
const getStaffName = (id) => {
  const s = staffList.value.find(x => x.id === id)
  return s ? s.name : '未知'
}

const getProgramName = (id) => {
  const p = programs.value.find(x => x.id === id)
  return p ? p.name : '未指定節目'
}

const getShiftsForDate = (dateStr) => {
  return monthlyShifts.value.filter(shift => shift.date === dateStr)
}

// 5. 互動邏輯
const goToToday = () => {
  currentYear.value = today.getFullYear()
  currentMonth.value = today.getMonth() + 1
}

const prevMonth = () => {
  if (currentMonth.value === 1) { 
    currentMonth.value = 12; currentYear.value-- 
  } else { 
    currentMonth.value-- 
  }
}

const nextMonth = () => {
  if (currentMonth.value === 12) { 
    currentMonth.value = 1; currentYear.value++ 
  } else { 
    currentMonth.value++ 
  }
}

// 準備迎接 Vue Router：點擊日期直接跳轉到獨立的日報表路由
const openDailyDetail = (dateStr) => {
  router.push({ path: '/admin/daily-detail', query: { date: dateStr } })
}
</script>
