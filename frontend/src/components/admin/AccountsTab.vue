<template>
  <div class="grid grid-cols-1 md:grid-cols-3 gap-8 animate-fade-in">
    <!-- 左側：新增帳號 -->
    <div class="md:col-span-1 bg-white p-6 rounded-xl shadow-sm border h-fit">
      <h3 class="text-lg font-bold text-gray-800 mb-4 border-b pb-2">新增系統帳號</h3>
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">帳號名稱</label>
          <input
            v-model="newUser.username"
            @keydown.enter="handleEnter"
            type="text"
            placeholder="請輸入登入帳號"
            class="w-full border border-gray-300 rounded-lg p-2 outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">登入密碼</label>
          <input
            v-model="newUser.password"
            @keydown.enter="handleEnter"
            type="password"
            placeholder="至少 8 碼"
            class="w-full border border-gray-300 rounded-lg p-2 outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">系統角色</label>
          <select
            v-model="newUser.role"
            class="w-full border border-gray-300 rounded-lg p-2 outline-none bg-white focus:ring-2 focus:ring-blue-500"
          >
            <option value="staff">後製技師 (Staff)</option>
            <option value="producer">製作人 (Producer)</option>
            <option value="admin">系統管理員 (Admin)</option>
          </select>
        </div>
        <button
          @click="addUser"
          class="w-full bg-blue-600 text-white py-2.5 rounded-lg hover:bg-blue-700 font-bold transition-colors shadow-sm"
        >
          建立帳號
        </button>
        <p class="text-[10px] text-gray-400 mt-2">註：若是建立「員工」帳號，建議前往「組織與人員」頁面一併建檔。</p>
      </div>
    </div>

    <!-- 右側：帳號列表 -->
    <div class="md:col-span-2 bg-white p-6 rounded-xl shadow-sm border">
      <h3 class="text-lg font-bold text-gray-800 mb-4 border-b pb-2">系統登入帳號清單</h3>
      <div class="overflow-y-auto max-h-[500px] custom-scrollbar pr-2">
        <div v-if="!users || users.length === 0" class="text-center text-gray-400 py-8">
          尚未建立任何帳號
        </div>
        <ul v-else class="space-y-2">
          <li v-for="user in users" :key="user.id" class="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-200">
            <div>
              <p class="font-bold text-gray-800">{{ user.username }}</p>
              <span :class="['role-badge', user.role ? 'role-' + user.role : 'role-unknown']">{{ user.role }}</span>
            </div>
            <button v-if="user.username !== 'admin'" @click="deleteUser(user.id)" class="text-gray-400 hover:text-red-500 font-bold text-xl transition-colors">&times;</button>
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
import { useAuthStore } from '@/stores/auth'
import { useToast } from 'vue-toastification'
import api from '@/api'

const toast = useToast()
const authStore = useAuthStore()
const scheduleStore = useScheduleStore()
const { users } = storeToRefs(scheduleStore)

const newUser = ref({
  username: '',
  password: '',
  role: 'producer'
})

const handleEnter = (e) => {
  if (e.isComposing || e.keyCode === 229) return
  addUser()
}

const addUser = async () => {
  if (!newUser.value.username || !newUser.value.password) {
    return toast.warning("請填寫帳號與密碼！")
  }
  try {
    await api.post('/users', {
      username: newUser.value.username.trim(),
      password: newUser.value.password,
      role: newUser.value.role
    })
    toast.success("帳號建立成功")
    newUser.value = { username: '', password: '', role: 'producer' }
    await scheduleStore.fetchAllData(authStore.role)
  } catch (e) {
    toast.error("建立失敗：" + (e.response?.data?.detail || e.message))
  }
}

const props = defineProps({
  showConfirm: Function
})

const deleteUser = async (id) => {
  const ok = props.showConfirm
    ? await props.showConfirm('確定註銷此帳號嗎？此動作無法復原。', 'cancel')
    : confirm('確定註銷此帳號嗎？此動作無法復原。')

  if (!ok) return
  try {
    await api.delete(`/users/${id}`);
    toast.success("註銷成功");
    await scheduleStore.fetchAllData(authStore.role);
  } catch (e) {
    toast.error("註銷失敗：" + (e.response?.data?.detail || "請檢查該帳號是否仍關聯員工"));
  }
}
</script>

<style scoped>
.role-badge {
  @apply px-2 py-0.5 text-xs font-semibold rounded-full;
}
.role-admin {
  @apply bg-red-100 text-red-800;
}
.role-producer {
  @apply bg-blue-100 text-blue-800;
}
.role-staff {
  @apply bg-green-100 text-green-800;
}
.role-unknown {
  @apply bg-gray-100 text-gray-800;
}
</style>
