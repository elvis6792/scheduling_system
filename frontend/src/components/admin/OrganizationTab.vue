<template>
  <div class="grid grid-cols-1 md:grid-cols-3 gap-8 animate-fade-in">
    <!-- 上方：新增人員 -->
    <div class="md:col-span-3 bg-white p-6 rounded-xl shadow-sm border">
      <h3 class="text-lg font-bold text-gray-800 mb-4 border-b pb-2">新增人員與帳號</h3>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">人員姓名</label>
          <input v-model="newStaff.name" type="text" class="w-full border border-gray-300 rounded-lg p-2 outline-none focus:ring-2 focus:ring-blue-500" placeholder="例如：王大明">
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">所屬部門</label>
          <select v-model="newStaff.department_id" class="w-full border border-gray-300 rounded-lg p-2 outline-none focus:ring-2 focus:ring-blue-500 bg-white" required>
            <option disabled :value="null">請選擇部門</option>
            <option v-for="dept in departments" :key="dept.id" :value="dept.id">{{ dept.name }}</option>
          </select>
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">每日工時 (小時)</label>
          <input v-model.number="newStaff.daily_work_hours" type="number" step="0.5" class="w-full border border-gray-300 rounded-lg p-2 outline-none focus:ring-2 focus:ring-blue-500">
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">登入帳號</label>
          <input v-model="newStaff.username" type="text" class="w-full border border-gray-300 rounded-lg p-2 outline-none focus:ring-2 focus:ring-blue-500" placeholder="英文或數字">
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">登入密碼</label>
          <input v-model="newStaff.password" type="password" class="w-full border border-gray-300 rounded-lg p-2 outline-none focus:ring-2 focus:ring-blue-500" placeholder="至少 8 碼">
        </div>
        <div class="flex items-end">
          <button @click="createStaffWithUser" class="w-full bg-blue-600 text-white py-2.5 rounded-lg hover:bg-blue-700 font-bold transition-colors">建立人員與帳號</button>
        </div>
      </div>
    </div>

    <!-- 左側：部門管理 -->
    <div class="md:col-span-1 bg-white p-6 rounded-xl shadow-sm border">
      <h3 class="text-lg font-bold text-gray-800 mb-4 border-b pb-2">部門管理</h3>
      <div class="flex items-center space-x-2 mb-4">
        <input v-model="newDeptName" @keydown.enter="handleDeptEnter" type="text" class="w-full border border-gray-300 rounded-lg p-2 outline-none focus:ring-2 focus:ring-teal-500" placeholder="新增部門名稱">
        <button @click="addDepartment" class="bg-teal-600 text-white px-4 py-2 rounded-lg hover:bg-teal-700 font-bold transition-colors whitespace-nowrap">新增</button>
      </div>
      <div class="overflow-y-auto max-h-[400px] custom-scrollbar pr-2" v-if="departments.length > 0">
        <ul class="space-y-2">
          <li v-for="dept in departments" :key="dept.id" class="flex items-center justify-between p-2 bg-gray-50 rounded-lg border border-gray-200">
            <span class="font-medium text-gray-700">{{ dept.name }}</span>
            <button @click="deleteDepartment(dept.id)" class="text-gray-400 hover:text-red-500 font-bold text-xl transition-colors">&times;</button>
          </li>
        </ul>
      </div>
      <div v-else class="text-center text-gray-400 py-8">
        尚未建立任何部門
      </div>
    </div>

    <!-- 中間：人員列表 -->
    <div class="md:col-span-2 bg-white p-6 rounded-xl shadow-sm border">
      <h3 class="text-lg font-bold text-gray-800 mb-4 border-b pb-2">人員列表</h3>
      <div class="overflow-y-auto max-h-[500px] custom-scrollbar pr-2">
        <div v-if="staffList.length === 0" class="text-center text-gray-400 py-8">
          尚未建立任何人員
        </div>
        <ul v-else class="space-y-3">
          <li v-for="staff in staffList" :key="staff.id" class="p-3 bg-gray-50 rounded-lg border border-gray-200 hover:shadow-sm transition-shadow">
            <div class="flex items-center justify-between">
              <div>
                <p class="font-bold text-gray-800">{{ staff.name }}</p>
                <p class="text-xs text-gray-500">{{ getDeptName(staff.department_id) }}</p>
              </div>
              <div class="flex items-center space-x-3">
                <div class="flex items-center space-x-1">
                  <input 
                    :value="staff.daily_work_hours"
                    @input="staff.daily_work_hours = Number($event.target.value) || 0"
                    @change="updateStaffHours(staff)"
                    type="number" 
                    step="0.5" 
                    class="w-16 text-center border border-gray-300 rounded-md p-1 text-sm outline-none focus:ring-2 focus:ring-blue-500"
                  >
                  <span class="text-xs text-gray-500">hr/日</span>
                </div>
                <button @click="deleteStaff(staff.id)" class="text-gray-400 hover:text-red-500 font-bold text-xl transition-colors">&times;</button>
              </div>
            </div>
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
// 1. 直接從 Pinia 拿回全域的部門與員工陣列
const { departments, staffList } = storeToRefs(scheduleStore)

// 2. 宣告專屬表單變數
const newDeptName = ref('')
const newStaff = ref({
  name: '',
  department_id: null,
  username: '',
  password: '',
  role: 'staff',
  daily_work_hours: 9.0
})

// 3. 輔助函數
const getDeptName = (id) => {
  const d = departments.value.find(x => x.id === id)
  return d ? d.name : '未知'
}

const handleDeptEnter = (e) => {
  if (e.isComposing || e.keyCode === 229) return
  addDepartment()
}

const props = defineProps({
  showConfirm: Function
})

// 4. 部門管理邏輯
const addDepartment = async () => {
  if (!newDeptName.value.trim()) return
  try {
    await api.post('/departments', { name: newDeptName.value })
    newDeptName.value = ''
    toast.success("新增成功")
    await scheduleStore.fetchAllData('admin')
  } catch (e) {
    toast.error("新增失敗")
  }
}

const deleteDepartment = async (id) => {
  const confirmFn = props.showConfirm || window.confirm;
  const ok = await confirmFn('確定刪除此部門嗎？', 'cancel');
  if (!ok) return;
  try {
    await api.delete(`/departments/${id}`)
    toast.success("刪除成功")
    await scheduleStore.fetchAllData('admin')
  } catch (e) {
    toast.error("刪除失敗")
  }
}

// 5. 人員管理邏輯
const createStaffWithUser = async (event) => {
  if (event && event.isComposing) return
  if (!newStaff.value.name || !newStaff.value.username || !newStaff.value.password || !newStaff.value.department_id) {
    return toast.warning("請填寫完整的人員姓名、部門與帳號密碼資訊！")
  }
  try {
    // 呼叫後端合併後的「同步建立人員與帳號」API
    await api.post('/staff', {
      name: newStaff.value.name,
      department_id: newStaff.value.department_id,
      daily_work_hours: newStaff.value.daily_work_hours,
      username: newStaff.value.username,
      password: newStaff.value.password,
      role: newStaff.value.role,
    })

    toast.success("人員與帳號建立成功！")
    newStaff.value = { name: '', department_id: null, username: '', password: '', role: 'staff', daily_work_hours: 9.0 }
    
    await scheduleStore.fetchAllData('admin')
  } catch (error) {
    toast.error("新增失敗：" + (error.response?.data?.detail || "系統錯誤"))
  }
}

const updateStaffHours = async (staff) => {
  if (!staff.daily_work_hours || staff.daily_work_hours <= 0) return toast.warning("請輸入有效的工時！")
  try {
    await api.put(`/staff/${staff.id}`, { daily_work_hours: staff.daily_work_hours })
    toast.success(`${staff.name} 的工時已更新`)
    await scheduleStore.fetchAllData('admin')
  } catch(e) {
    toast.error("更新失敗：" + (e.response?.data?.detail || e.message))
  }
}

const deleteStaff = async (id) => {
  const confirmFn = props.showConfirm || window.confirm;
  const ok = await confirmFn('確定移除此員工嗎？', 'cancel');
  if (!ok) return;
  try {
    await api.delete(`/staff/${id}`)
    toast.success("移除成功")
    await scheduleStore.fetchAllData('admin')
  } catch (e) {
    toast.error("移除失敗")
  }
}
</script>