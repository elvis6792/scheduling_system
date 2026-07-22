<template>
  <div class="grid grid-cols-1 md:grid-cols-3 gap-8 mb-6">
    <!-- 左側：新節目登記 -->
    <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-100 space-y-4 h-fit">
      <h2 class="text-xl font-bold text-gray-800 border-b pb-2">新節目登記</h2>

      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">節目名稱</label>
          <input
            v-model="newProg.name"
            @keydown.enter="handleEnter"
            type="text"
            class="w-full border border-gray-300 rounded-lg p-2 outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="請輸入節目名稱"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">預估工時 (小時)</label>
          <input
            v-model.number="newProg.estimated_hours"
            type="number"
            step="0.5"
            class="w-full border border-gray-300 rounded-lg p-2 outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">節目識別色</label>
          <div class="flex flex-wrap gap-2">
            <div v-for="color in presetColors" :key="color"
                 @click="newProg.color = color"
                 :class="['w-8 h-8 rounded-full cursor-pointer shadow-sm border-2 transition-transform hover:scale-110 flex items-center justify-center', newProg.color === color ? 'border-gray-800 scale-110' : 'border-transparent']"
                 :style="{ backgroundColor: color }">
                 <svg v-if="newProg.color === color" class="w-4 h-4 text-white drop-shadow-md" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                   <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"></path>
                 </svg>
            </div>
          </div>
        </div>

        <button
          @click="addProgram"
          class="w-full bg-blue-600 text-white py-2.5 rounded-lg hover:bg-blue-700 font-bold transition-colors shadow-sm"
        >
          確認建檔
        </button>
      </div>
    </div>

    <!-- 右側：現有節目列表 -->
    <div class="md:col-span-2 bg-white p-6 rounded-xl shadow-sm border border-gray-100">
      <h2 class="text-xl font-bold text-gray-800 mb-4 border-b pb-2">現有節目清單</h2>

      <div v-if="!programs || programs.length === 0" class="text-center py-12 text-gray-400">
        <p>目前尚無節目資料，請由左側新增。</p>
      </div>

      <div v-else class="overflow-x-auto">
        <table class="w-full text-left border-collapse">
          <thead>
            <tr class="border-b text-gray-500 text-sm">
              <th class="pb-3 font-semibold">節目名稱</th>
              <th class="pb-3 font-semibold">預估工時</th>
              <th class="pb-3 font-semibold text-right">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100">
            <tr v-for="p in programs" :key="p.id" class="hover:bg-gray-50 transition-colors group">
              <td class="py-4 font-medium flex items-center">
                <div :style="{ backgroundColor: p.color || '#6366f1' }" class="w-3.5 h-3.5 rounded-full mr-3 shadow-sm border border-gray-200"></div>
                <span class="text-gray-800">{{ p.name }}</span>
              </td>
              <td class="py-4 text-gray-600 font-medium">{{ p.estimated_hours }} hr</td>
              <td class="py-4 text-right">
                <button
                  @click="deleteProgram(p.id)"
                  class="text-gray-400 hover:text-red-600 text-sm px-3 py-1.5 hover:bg-red-50 rounded-lg transition-all font-bold"
                >
                  刪除
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useScheduleStore } from '@/stores/schedule'
import { useAuthStore } from '@/stores/auth'
import { useToast } from 'vue-toastification'
import api from '@/api'

const toast = useToast()
const authStore = useAuthStore()
const scheduleStore = useScheduleStore()
const { programs } = storeToRefs(scheduleStore)

const presetColors = [
  '#ef4444', '#f97316', '#f59e0b', '#10b981', '#06b6d4',
  '#3b82f6', '#6366f1', '#8b5cf6', '#d946ef', '#ec4899', '#64748b'
]

const newProg = ref({
  name: '',
  estimated_hours: 8.0,
  color: '#6366f1'
})

const handleEnter = (e) => {
  if (e.isComposing || e.keyCode === 229) return
  addProgram()
}

const addProgram = async () => {
  if (!newProg.value.name.trim()) {
    toast.warning("請輸入節目名稱")
    return
  }

  try {
    await api.post('/programs', {
      name: newProg.value.name.trim(),
      estimated_hours: Number(newProg.value.estimated_hours) || 0,
      color: newProg.value.color
    })
    newProg.value = { name: '', estimated_hours: 8.0, color: '#6366f1' }
    toast.success("節目建檔成功")
    await scheduleStore.fetchAllData(authStore.role)
  } catch (e) {
    toast.error("建檔失敗：" + (e.response?.data?.detail || e.message))
  }
}

const props = defineProps({
  showConfirm: Function
})

const deleteProgram = async (id) => {
  console.log("Delete program id:", id);
  const confirmFn = props.showConfirm || window.confirm;
  const ok = await confirmFn('確定刪除此節目嗎？這可能影響現有班表的顯示。', 'cancel');

  if (!ok) return;

  try {
    await api.delete(`/programs/${id}`)
    toast.success("刪除成功")
    await scheduleStore.fetchAllData(authStore.role)
  } catch (e) {
    toast.error("刪除失敗")
  }
}

onMounted(async () => {
  // 確保進入此頁面時資料是鮮活的
  if (programs.value.length === 0) {
    await scheduleStore.fetchAllData(authStore.role)
  }
})
</script>
