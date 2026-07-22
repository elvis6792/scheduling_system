<template>
  <div class="min-h-screen bg-gray-50 p-8 font-sans relative">

    <div v-if="confirmModal.show" class="fixed inset-0 z-50 flex items-center justify-center bg-gray-900 bg-opacity-40 backdrop-blur-sm transition-opacity">
      <div class="bg-white rounded-2xl shadow-2xl w-full max-w-sm overflow-hidden" style="animation: popUp 0.2s ease-out;">
        <div class="p-6 text-center">
          <div :class="{'bg-red-100 text-red-600': confirmModal.actionType === 'cancel', 'bg-orange-100 text-orange-600': confirmModal.actionType === 'update', 'bg-purple-100 text-purple-600': confirmModal.actionType === 'create'}" class="w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-4 transition-colors">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>
          </div>
          <h3 class="text-lg font-bold text-gray-900 mb-2">
            {{ confirmModal.actionType === 'cancel' ? '確認執行註銷' : (confirmModal.actionType === 'update' ? '確認執行修改' : '確認執行操作') }}
          </h3>
          <p class="text-sm text-gray-500 leading-relaxed whitespace-pre-line">{{ confirmModal.message }}</p>
        </div>
        <div class="p-4 bg-gray-50 border-t border-gray-100">
          <div class="flex space-x-3">
            <button @click="handleCancelConfirm" class="flex-1 bg-gray-200 text-gray-800 py-2.5 rounded-lg font-bold hover:bg-gray-300 transition-colors">取消</button>
            <button @click="handleAcceptConfirm" class="flex-1 bg-blue-600 text-white py-2.5 rounded-lg font-bold hover:bg-blue-700 shadow-md transition-colors">確定</button>
          </div>
        </div>
      </div>
    </div>

    <header class="mb-8 flex justify-between items-center bg-white p-6 rounded-xl shadow-sm border border-gray-100">
      <div><h1 class="text-2xl font-bold text-gray-800 tracking-wide">排班管理中心</h1></div>
      <div class="flex items-center space-x-4">
        <span class="text-gray-600 font-medium">你好，{{ currentUsername }}</span>
        <button @click="openPasswordModal" class="text-gray-500 hover:text-blue-600 transition-colors font-medium text-sm">修改密碼</button>
        <button @click="logout" class="bg-red-50 text-red-600 px-4 py-2 rounded-lg hover:bg-red-100 transition-colors font-medium">登出系統</button>
      </div>
    </header>

    <div class="mb-6">
      <nav class="flex space-x-2 border-b border-gray-200 pb-2 overflow-x-auto">
        <button v-if="canAccessAgent" @click="router.push('/admin/agent')" :class="route.path.includes('/admin/agent') ? 'bg-purple-600 text-white' : 'bg-white text-gray-600'" class="px-6 py-2 rounded-lg font-bold shadow-sm">AI Agent</button>
        <button @click="router.push('/admin/calendar')" :class="route.path.includes('/admin/calendar') ? 'bg-blue-600 text-white' : 'bg-white text-gray-600'" class="px-6 py-2 rounded-lg font-bold shadow-sm">班表總覽</button>
        <button @click="router.push('/admin/matrix')" :class="route.path.includes('/admin/matrix') ? 'bg-indigo-600 text-white' : 'bg-white text-gray-600'" class="px-6 py-2 rounded-lg font-bold shadow-sm">
          <span v-if="isStaff">我的排班與休假</span>
          <span v-else>全公司總表與排班</span>
        </button>
        <button v-if="isAdmin || isProducer" @click="router.push('/admin/schedule')" :class="route.path.includes('/admin/schedule') ? 'bg-green-600 text-white' : 'bg-white text-gray-600'" class="px-6 py-2 rounded-lg font-bold shadow-sm">快速排班</button>
        <button v-if="isAdmin" @click="router.push('/admin/settlement')" :class="route.path.includes('/admin/settlement') ? 'bg-orange-600 text-white' : 'bg-white text-gray-600'" class="px-6 py-2 rounded-lg font-bold shadow-sm">工時結算</button>
        <template v-if="isAdmin">
          <button @click="router.push('/admin/organization')" :class="route.path.includes('/admin/organization') ? 'bg-teal-600 text-white' : 'bg-white text-gray-600'" class="px-6 py-2 rounded-lg font-bold shadow-sm">組織與人員</button>
          <button @click="router.push('/admin/programs')" :class="route.path.includes('/admin/programs') ? 'bg-blue-600 text-white' : 'bg-white text-gray-600'" class="px-6 py-2 rounded-lg font-bold shadow-sm">節目建檔</button>
          <button @click="router.push('/admin/accounts')" :class="route.path.includes('/admin/accounts') ? 'bg-cyan-600 text-white' : 'bg-white text-gray-600'" class="px-6 py-2 rounded-lg font-bold shadow-sm">帳號權限</button>
          <button @click="router.push('/admin/system_settings')" :class="route.path.includes('/admin/system_settings') ? 'bg-yellow-600 text-white' : 'bg-white text-gray-600'" class="px-6 py-2 rounded-lg font-bold shadow-sm">系統設定</button>
        </template>
      </nav>
    </div>

    <router-view v-slot="{ Component }">
      <component
        :is="Component"
        v-model:userInput="userInput"
        :chatLog="chatLog"
        :isLoading="isLoading"
        :showConfirm="showConfirm"
        :show-confirm="showConfirm"
        @send-message="handleSendMessage"
        @clear-chat="clearChat"
        @cancel-request="cancelAgentRequest"
        @cell-click="handleCellClick"
        @open-shift-edit-modal="openShiftEditModal"
        @delete-shift="deleteShift"
        @back-to-calendar="router.push('/admin/calendar')"
      />
    </router-view>

    <CellActionModal
      v-model:show="showCellModal"
      v-model:cellActionTab="cellActionTab" 
      v-model:newShift="newShift"
      v-model:newLeave="newLeave"
      v-model:tempDailyLimit="tempDailyLimit" 
      :isAdmin="isAdmin"
      :isProducer="isProducer"
      :activeCell="activeCell"
      :existingShiftId="existingShiftId"
      :existingLeaveId="existingLeaveId"
      :leaveTypes="leaveTypes"
      :staffOfSameDept="staffOfSameDept"
      @save-override="saveOverride"
      @submit-leave="submitLeave"
      @remove-leave="removeLeave"
      @submit-shift="submitShift"
      @remove-shift="removeShift"
    />

    <AiAuthModals
      v-model:showCancelAll="showCancelAllModal"
      v-model:showSwap="showSwapModal"
      v-model:showLeaveReallocate="showLeaveReallocateModal"
      v-model:showCoverage="showCoverageModal"
      v-model:showCreateShift="showCreateShiftModal"
      :activeToolPayload="activeToolPayload"
      :createShiftPayload="createShiftPayload"
      :createShiftDisplay="createShiftDisplay"
      @execute-cancel-all="executeCancelAll"
      @execute-swap="executeSwap"
      @execute-leave-reallocate="executeLeaveReallocate"
      @execute-create-shift="confirmCreateShift"
      @cancel-create-shift="cancelCreateShift"
    />

    <PasswordUpdateModal v-model:show="showPasswordModal" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import type { Ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { storeToRefs } from 'pinia'
import api from '../api'

// --- TypeScript 類型定義 ---
interface Staff {
  id: number;
  name: string;
  department_id: number;
  daily_work_hours: number;
}
interface Program {
  id: number;
  name: string;
  estimated_hours: number;
}
interface Shift {
  id: number;
  date: string;
  start_time: string;
  end_time: string;
  department_id: number;
  staff_id: number;
  program_id: number;
}
interface ToolPayload {
  month?: string;
  date?: string;
  start_date?: string;
  end_date?: string;
  department_keyword?: string;
  staff_keyword?: string;
  [key: string]: any;
}
interface CreateShiftPayload {
  date: string;
  start_time: string;
  end_time: string;
  department_id: number;
  staff_id: number;
  program_id: number;
  notes?: string;
}
interface CreateShiftDisplay {
  content: string;
  staff_name: string;
  prog_name: string;
}

import { useAuthStore } from '../stores/auth';
import { useScheduleStore } from '../stores/schedule';
import CellActionModal from '../components/admin/CellActionModal.vue';
import AiAuthModals from '../components/admin/AiAuthModals.vue';
import PasswordUpdateModal from '../components/admin/PasswordUpdateModal.vue';
import { useToast } from 'vue-toastification'
import { useMatrix } from '../composables/useMatrix.js'
import { calculateHoursDiff } from '../utils/timeUtils'
import { useAiActions } from '../composables/useAiActions'

const authStore = useAuthStore()
const { role: userRole, staffId: currentStaffId } = storeToRefs(authStore)
const scheduleStore = useScheduleStore()

const {
  staffList, programs, leaves, monthlyShifts,
  currentYear, currentMonth, userInput, chatLog, isLoading
} = storeToRefs(scheduleStore)

const { sendToAgent, clearChat, cancelAgentRequest } = scheduleStore;

const fetchData = async () => {
  await scheduleStore.fetchAllData(userRole.value as string);
};

const getStaffName = (id: number) => {
  return staffList.value.find((s: any) => s.id === id)?.name || '未知';
};

const isStaff = computed(() => (userRole.value as any) === 'staff');
const isAdmin = computed(() => (userRole.value as any) === 'admin');
const isProducer = computed(() => (userRole.value as any) === 'producer');
const canAccessAgent = computed(() => ['admin', 'producer', 'staff'].includes((userRole.value as any)));

const showPasswordModal = ref(false)
const openPasswordModal = () => {
  showPasswordModal.value = true;
};

const activeToolPayload = ref<ToolPayload>({});
const showSwapModal = ref(false);
const showCancelAllModal = ref(false);
const showLeaveReallocateModal = ref(false);
const showCoverageModal = ref(false);

const { executeCancelAll, executeSwap, executeLeaveReallocate } = useAiActions({
  chatLog,
  isLoading,
  activeToolPayload,
  showCancelAllModal,
  showSwapModal,
  showLeaveReallocateModal,
  monthlyShifts,
  fetchData
});

const showCreateShiftModal = ref(false);
const createShiftPayload = ref<CreateShiftPayload>({} as CreateShiftPayload);
const createShiftDisplay = ref<CreateShiftDisplay>({} as CreateShiftDisplay);

const handleCreateShiftAction = (toolData: any) => {
  const payload = (toolData.payload || toolData) as CreateShiftPayload;
  createShiftPayload.value = payload;
  createShiftDisplay.value = {
    content: toolData.content || `AI 已為您生成一筆排班草案，請確認：`,
    staff_name: toolData.staff_name || '未指定',
    prog_name: toolData.prog_name || '未指定',
  };
  showCreateShiftModal.value = true;
};

const cancelCreateShift = () => {
  showCreateShiftModal.value = false;
  createShiftPayload.value = {} as CreateShiftPayload;
  createShiftDisplay.value = {} as CreateShiftDisplay;
};

const confirmCreateShift = async () => {
  try {
    isLoading.value = true;
    showCreateShiftModal.value = false;
    const apiPayload = { ...createShiftPayload.value };
    await api.post('/shifts', apiPayload);
    chatLog.value.push({
      sender: 'agent' as any,
      text: `排班已成功寫入！\n- 日期：${apiPayload.date}\n- 人員：${createShiftDisplay.value.staff_name}\n- 節目：${createShiftDisplay.value.prog_name}`
    });
    await fetchData();
  } catch (error: any) {
    const errorMsg = error.response?.data?.detail || error.message;
    chatLog.value.push({ sender: 'agent', text: `寫入排班時發生錯誤：${errorMsg}` });
  } finally {
    isLoading.value = false;
    createShiftPayload.value = {} as CreateShiftPayload;
    createShiftDisplay.value = {} as CreateShiftDisplay;
  }
};

const activeCell = ref<{ staff_id: number | null, date: string, staff_name: string }>({ staff_id: null, date: '', staff_name: '' });
const leaveTypes: string[] = ['特休', '例假日', '休假日', '補休', '病假', '事假'];
const newLeave = ref<{ staff_id: number | string; date: string; leave_type: string; hours: number }>({ staff_id: 0, date: '', leave_type: '特休', hours: 8.0 });
const showCellModal = ref(false);
const cellActionTab = ref('leave');
const existingLeaveId = ref<number | null>(null);
const existingShiftId = ref<number | null>(null);
const tempDailyLimit = ref(8);

const newShift = ref({
  staff_id: null as number | null,
  program_id: '',
  department_id: null as number | null,
  duration: 0,
  start_time: '09:00',
  end_time: '18:00',
});

const staffOfSameDept = computed(() => {
  if (!newShift.value.department_id) return [];
  return staffList.value.filter((s: Staff) => s.department_id === newShift.value.department_id);
});

const submitLeave = async () => {
   await addLeave();
   showCellModal.value = false;
   await scheduleStore.fetchAllData(userRole.value as string);
};
const removeLeave = async (id: number) => {
   showCellModal.value = false;
   await deleteLeave(id);
   await scheduleStore.fetchAllData(userRole.value as string);
};

const router = useRouter()
const route = useRoute();
const toast = useToast();

const confirmModal = ref<{
  show: boolean;
  message: string;
  actionType: 'create' | 'cancel' | 'update';
  resolve: ((value: boolean) => void) | null;
}>({ show: false, message: '', actionType: 'create', resolve: null })

const showConfirm = (message: string, actionType: 'create' | 'cancel' | 'update' = 'create'): Promise<boolean> => {
  return new Promise((resolve) => { confirmModal.value = { show: true, message, actionType, resolve: resolve as any } })
}
const handleAcceptConfirm = () => { if (confirmModal.value.resolve) confirmModal.value.resolve(true); confirmModal.value.show = false }
const handleCancelConfirm = () => { if (confirmModal.value.resolve) confirmModal.value.resolve(false); confirmModal.value.show = false }

const handleSendMessage = () => {
  sendToAgent(userRole.value as string, actionHandlers);
};

const actionHandlers: any = {
  'cancel_all': (data: any) => { activeToolPayload.value = data; showCancelAllModal.value = true; },
  'swap_shifts': (data: any) => { activeToolPayload.value = data; showSwapModal.value = true; },
  'reallocate_leave': (data: any) => { activeToolPayload.value = data; showLeaveReallocateModal.value = true; },
  'check_coverage': (data: any) => { activeToolPayload.value = data; showCoverageModal.value = true; },
  'create_shift': handleCreateShiftAction,
};

const currentUsername = computed<string>(() => {
  const token = authStore.token;
  if (!token) return '';
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return (payload.sub as string) || '';
  } catch (e) {
    return '';
  }
});

const { shiftMatrixMap, leaveMatrixMap } = useMatrix(currentYear, currentMonth, monthlyShifts, leaves);

const saveOverride = async () => {
  if (userRole.value !== 'admin') {
    toast.error('權限不足：僅有管理員可以臨時調整上班時數。');
    return;
  }
  if (!activeCell.value.staff_id) return;
  try {
    await api.post('/work-hours-override', {
      staff_id: activeCell.value.staff_id,
      date: activeCell.value.date,
      hours: tempDailyLimit.value,
    });
    toast.success('臨時工時調整成功！');
    await scheduleStore.fetchAllData(userRole.value as string);
  } catch (error: any) {
    toast.error('調整失敗：' + (error.response?.data?.detail || error.message));
  }
};

const handleCellClick = (staffId: number, dateStr: string, staffName: string, deptId: number) => {
  if (userRole.value === 'staff') {
    if (!currentStaffId.value || String(staffId) !== String(currentStaffId.value)) {
      toast.error("權限不足：您只能編輯與登錄「自己」的班表與休假喔！");
      return;
    }
  }
  activeCell.value = { staff_id: staffId, date: dateStr, staff_name: staffName };
  const staffMember = staffList.value.find((s: Staff) => s.id === staffId);
  tempDailyLimit.value = staffMember ? staffMember.daily_work_hours : 8.0;

  const eLeave = (leaveMatrixMap.value as any)[staffId]?.[dateStr];
  if (eLeave) {
    existingLeaveId.value = eLeave.id;
    newLeave.value = { staff_id: staffId, date: dateStr, leave_type: eLeave.leave_type, hours: eLeave.hours };
  } else {
    existingLeaveId.value = null;
    newLeave.value = { staff_id: staffId, date: dateStr, leave_type: '特休', hours: 8.0 };
  }

  const shiftsOnDay = (shiftMatrixMap.value as any)[staffId]?.[dateStr];
  const eShift = shiftsOnDay && shiftsOnDay.length > 0 ? shiftsOnDay[0] : null;

  if (eShift) {
    existingShiftId.value = eShift.id;
    newShift.value = {
      staff_id: staffId,
      program_id: String(eShift.program_id),
      department_id: deptId,
      duration: calculateHoursDiff(eShift.start_time, eShift.end_time),
      start_time: eShift.start_time.slice(0,5),
      end_time: eShift.end_time.slice(0,5)
    };
  } else {
    existingShiftId.value = null;
    newShift.value = {
      staff_id: staffId,
      program_id: '',
      department_id: deptId,
      duration: 8,
      start_time: '09:00',
      end_time: '17:00'
    };
  }

  if (userRole.value === 'staff') cellActionTab.value = 'leave';
  else if (userRole.value === 'producer') cellActionTab.value = 'shift';
  else cellActionTab.value = eShift ? 'shift' : (eLeave ? 'leave' : 'shift');

  showCellModal.value = true;
};

const openShiftEditModal = (shift: Shift) => {
  if (userRole.value === 'staff' && String(shift.staff_id) !== String(currentStaffId.value)) {
    toast.error("權限不足：您只能修改自己的排班！");
    return;
  }
  activeCell.value = { staff_id: shift.staff_id, date: shift.date, staff_name: getStaffName(shift.staff_id) };
  existingShiftId.value = shift.id;
  newShift.value = {
    staff_id: shift.staff_id,
    program_id: String(shift.program_id),
    start_time: shift.start_time.slice(0,5),
    end_time: shift.end_time.slice(0,5),
    duration: calculateHoursDiff(shift.start_time, shift.end_time),
    department_id: shift.department_id
  };
  cellActionTab.value = 'shift';
  showCellModal.value = true;
};

const addLeave = async () => {
  if (!newLeave.value.staff_id || !newLeave.value.date) return toast.warning("請選擇人員與日期！");
  try {
    await api.post('/leaves', newLeave.value);
    toast.success(`已登錄 ${activeCell.value.staff_name} 的休假`);
    await scheduleStore.fetchAllData(userRole.value as string);
  } catch (e: any) {
    toast.error(e.response?.data?.detail || "登錄失敗");
  }
};

const deleteLeave = async (id: number) => {
  if (!(await showConfirm('確定移除此休假紀錄嗎？', 'cancel'))) return;
  try {
    await api.delete(`/leaves/${id}`);
    toast.success("移除成功！");
    await scheduleStore.fetchAllData(userRole.value as string);
  } catch (e: any) {
    toast.error("移除失敗");
  }
};

const deleteShift = async (id: number) => {
  if (await showConfirm('確定刪除此筆排班嗎？', 'cancel')) {
    try {
      await api.delete(`/shifts/${id}`);
      toast.success("刪除成功！");
      await scheduleStore.fetchAllData(userRole.value as string);
    } catch (e: any) {
      toast.error("刪除失敗");
    }
  }
};

const submitShift = async () => {
  if (!newShift.value.program_id) return toast.warning("請選擇節目！");
  try {
    const payload = {
      staff_id: activeCell.value.staff_id,
      date: activeCell.value.date,
      program_id: Number(newShift.value.program_id),
      department_id: newShift.value.department_id,
      duration: newShift.value.duration,
      start_time: newShift.value.start_time,
      end_time: newShift.value.end_time
    };

    if (existingShiftId.value) await api.put(`/shifts/${existingShiftId.value}`, payload);
    else await api.post('/shifts', payload);

    toast.success("儲存成功！");
    showCellModal.value = false;
    await scheduleStore.fetchAllData(userRole.value as string);
  } catch (error: any) {
    toast.error("儲存失敗：" + (error.response?.data?.detail || error.message));
  }
};

const removeShift = async (id: number) => {
  showCellModal.value = false;
  await deleteShift(id);
};

watch(() => newShift.value.program_id, (newProgId) => {
  if (newProgId && !existingShiftId.value) {
    const program = programs.value.find((p: any) => String(p.id) === String(newProgId));
    if (program) {
      newShift.value.duration = program.estimated_hours;
      const [h, m] = newShift.value.start_time.split(':').map(Number);
      const endTotalMinutes = h * 60 + m + (program.estimated_hours * 60);
      const endH = Math.floor(endTotalMinutes / 60) % 24;
      const endM = endTotalMinutes % 60;
      newShift.value.end_time = `${String(endH).padStart(2, '0')}:${String(endM).padStart(2, '0')}`;
    }
  }
});

watch([currentYear, currentMonth], async () => {
  await scheduleStore.fetchAllData(userRole.value as string);
});

const logout = () => {
  authStore.clearToken();
  router.push('/login');
};

onMounted(async () => {
  await scheduleStore.fetchAllData(userRole.value as string);
  if (route.path === '/admin') {
    if (userRole.value === 'admin' || userRole.value === 'producer') router.push('/admin/agent');
    else router.push('/admin/calendar');
  }
});

</script>

<style scoped>
@import url('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css');
@keyframes popUp { from { transform: scale(0.9) translateY(10px); opacity: 0; } to { transform: scale(1) translateY(0); opacity: 1; } }
.animate-fade-in { animation: fadeIn 0.5s ease-out; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
</style>
