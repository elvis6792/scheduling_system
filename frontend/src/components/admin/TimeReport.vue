<template>
  <div class="mb-6 bg-white p-6 rounded-xl shadow-sm border border-gray-100 animate-fade-in">
    <h2 class="text-xl font-bold text-gray-800 mb-4 border-b pb-2">時數結算與報表</h2>

    <div class="flex flex-col md:flex-row gap-4 items-end mb-6 bg-gray-50 p-4 rounded-lg border border-gray-200">
      <div>
        <label class="block text-sm font-bold text-gray-700 mb-1">開始日期</label>
        <input v-model="statsRange.start" type="date" class="w-full border rounded-lg p-2 outline-none focus:ring-2 focus:ring-blue-500 bg-white" />
      </div>
      <div>
        <label class="block text-sm font-bold text-gray-700 mb-1">結束日期</label>
        <input v-model="statsRange.end" type="date" class="w-full border rounded-lg p-2 outline-none focus:ring-2 focus:ring-blue-500 bg-white" />
      </div>
      <button @click="generateReport" class="bg-blue-600 text-white px-8 py-2 rounded-lg font-bold hover:bg-blue-700 transition-colors shadow-sm">
        產生統計報表
      </button>
    </div>

    <div v-if="reportData.total > 0" class="grid grid-cols-1 md:grid-cols-4 gap-4 animate-fade-in">
      <div class="bg-gradient-to-br from-blue-50 to-blue-100 p-4 rounded-xl border border-blue-200 shadow-sm flex flex-col justify-center items-center">
        <span class="text-blue-700 font-bold text-sm">區間總工時</span>
        <span class="text-5xl font-black text-blue-700 mt-2">{{ reportData.total.toFixed(1) }}</span>
        <span class="text-xs text-blue-500 mt-1 font-bold">小時</span>
      </div>
      
      <div class="bg-white p-4 rounded-xl border border-gray-200 shadow-sm max-h-[200px] overflow-y-auto custom-scrollbar">
        <span class="block text-sm font-bold text-gray-500 mb-2 border-b pb-1">部門時數統計</span>
        <div v-for="(hours, deptId) in reportData.depts" :key="deptId" class="flex justify-between items-center py-1.5 text-sm border-b border-dashed border-gray-100 last:border-0">
          <span class="font-bold text-gray-700">{{ getDeptName(Number(deptId)) }}</span>
          <span class="font-bold text-blue-600">{{ hours.toFixed(1) }} <span class="text-xs text-gray-400">hr</span></span>
        </div>
      </div>

      <div class="bg-white p-4 rounded-xl border border-gray-200 shadow-sm max-h-[200px] overflow-y-auto custom-scrollbar">
        <span class="block text-sm font-bold text-gray-500 mb-2 border-b pb-1">個人時數統計</span>
        <div v-for="(hours, staffId) in reportData.staff" :key="staffId" class="flex justify-between items-center py-1.5 text-sm border-b border-dashed border-gray-100 last:border-0">
          <span class="font-bold text-gray-700">{{ getStaffName(Number(staffId)) }}</span>
          <span class="font-bold text-green-600">{{ hours.toFixed(1) }} <span class="text-xs text-gray-400">hr</span></span>
        </div>
      </div>

      <div class="bg-white p-4 rounded-xl border border-gray-200 shadow-sm max-h-[200px] overflow-y-auto custom-scrollbar">
        <span class="block text-sm font-bold text-gray-500 mb-2 border-b pb-1">節目時數統計</span>
        <div v-for="(hours, progId) in reportData.programs" :key="progId" class="flex justify-between items-center py-1.5 text-sm border-b border-dashed border-gray-100 last:border-0">
          <div class="flex items-center">
             <div :style="{ backgroundColor: getProgramColor(Number(progId)) }" class="w-3 h-3 rounded-full mr-2 shadow-sm"></div>
             <span class="font-bold text-gray-700">{{ getProgramName(Number(progId)) }}</span>
          </div>
          <span class="font-bold text-purple-600">{{ hours.toFixed(1) }} <span class="text-xs text-gray-400">hr</span></span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useScheduleStore } from '@/stores/schedule'
import { useToast } from 'vue-toastification'
import { calculateHoursDiff } from '@/utils/timeUtils'
import api from '@/api'

const toast = useToast()
const scheduleStore = useScheduleStore()
const { departments, staffList, programs } = storeToRefs(scheduleStore)

const getLocalDateString = (date) => {
  if (!date) return '';
  const d = new Date(date);
  return `${d.getFullYear()}-${(d.getMonth() + 1).toString().padStart(2, '0')}-${d.getDate().toString().padStart(2, '0')}`;
}

const statsRange = ref({
  start: getLocalDateString(new Date(new Date().getFullYear(), new Date().getMonth(), 1)),
  end: getLocalDateString(new Date(new Date().getFullYear(), new Date().getMonth() + 1, 0))
})

const reportData = ref({ total: 0, depts: {}, staff: {}, programs: {} })

const generateReport = async () => {
  toast.info("正在產生報表...")
  try {
    const res = await api.get('/shifts', {
      params: { start_date: statsRange.value.start, end_date: statsRange.value.end }
    })
    
    const newReport = { total: 0, depts: {}, staff: {}, programs: {} }
    res.data.forEach(shift => {
      const hours = calculateHoursDiff(shift.start_time, shift.end_time)
      newReport.total += hours
      newReport.depts[shift.department_id] = (newReport.depts[shift.department_id] || 0) + hours
      newReport.staff[shift.staff_id] = (newReport.staff[shift.staff_id] || 0) + hours
      newReport.programs[shift.program_id] = (newReport.programs[shift.program_id] || 0) + hours
    })
    
    reportData.value = newReport
    toast.success("報表已更新！")
  } catch (e) {
    toast.error("報表產生失敗")
  }
}

// 輔助顯示函數
const getDeptName = (id) => departments.value.find(d => d.id === id)?.name || '未知'
const getStaffName = (id) => staffList.value.find(s => s.id === id)?.name || '未知'
const getProgramName = (id) => programs.value.find(p => p.id === id)?.name || '未知節目'
const getProgramColor = (id) => programs.value.find(p => p.id === id)?.color || '#6366f1'
</script>
