<template>
  <div v-if="show" class="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 backdrop-blur-sm animate-fade-in" @click.self="closeModal" data-testid="cell-action-modal">
    <div class="bg-white rounded-2xl shadow-2xl p-6 w-full max-w-md border border-gray-100">
      <div class="flex justify-between items-center mb-4">
        <h3 class="text-xl font-bold text-gray-800">
          {{ activeCell.date }} ｜ {{ activeCell.staff_name }}
        </h3>
        <button @click="closeModal" class="text-gray-400 hover:text-red-500 font-bold text-2xl transition-colors">&times;</button>
      </div>

      <!-- 權限控制：Admin 可切換分頁，其餘角色依據權限顯示內容 -->
      <div class="flex border-b mb-4" v-if="isAdmin">
        <button @click="$emit('update:cellActionTab', 'shift')" :class="['flex-1 py-2 font-bold text-center border-b-2 transition-colors', cellActionTab === 'shift' ? 'border-purple-600 text-purple-600' : 'border-transparent text-gray-400 hover:text-gray-600']">工作排班</button>
        <button @click="$emit('update:cellActionTab', 'leave')" :class="['flex-1 py-2 font-bold text-center border-b-2 transition-colors', cellActionTab === 'leave' ? 'border-orange-500 text-orange-500' : 'border-transparent text-gray-400 hover:text-gray-600']">休假登錄</button>
      </div>
      <div class="mb-4 border-b pb-2" v-else>
        <span v-if="cellActionTab === 'shift'" class="font-bold text-purple-600 text-lg">工作排班</span>
        <span v-else class="font-bold text-orange-500 text-lg">休假登錄</span>
      </div>

      <div v-if="cellActionTab === 'leave'" class="space-y-4">
        <!-- ... (Leave content remains same) -->
        <div>
          <label class="block text-sm font-bold text-gray-700 mb-2">假別選擇</label>
          <div class="grid grid-cols-2 gap-2">
            <button v-for="type in leaveTypes" :key="type"
                    @click="$emit('update:newLeave', { ...props.newLeave, leave_type: type })"
                    :class="['py-2 px-3 rounded-lg text-sm font-bold border transition-all', newLeave.leave_type === type ? 'bg-orange-500 text-white border-orange-500 shadow-md' : 'bg-gray-50 text-gray-600 hover:bg-gray-100']">
              {{ type }}
            </button>
          </div>
        </div>
        <div>
          <label class="block text-sm font-bold text-gray-700 mb-2">請假時數 (小時)</label>
          <input :value="newLeave.hours" @input="$emit('update:newLeave', { ...props.newLeave, hours: Number(($event.target as HTMLInputElement).value) })" type="number" step="0.5" class="w-full border rounded-lg p-3 outline-none focus:ring-2 focus:ring-orange-500 font-bold bg-gray-50 text-center text-lg" />
        </div>

        <!-- 本日工時狀態 (同步顯示於休假分頁) -->
        <div class="mt-2 p-3 bg-gray-50 rounded-lg border border-gray-200 text-sm">
          <h4 class="font-bold text-gray-600 mb-2">本日工時狀態</h4>
          <div class="space-y-1">
            <div v-if="isAdmin" class="flex justify-between items-center">
              <span class="text-gray-500">上班時數：</span>
              <div class="flex items-center gap-2">
                <input type="number" step="0.5" :value="tempDailyLimit" @input="$emit('update:tempDailyLimit', Number(($event.target as HTMLInputElement).value))" class="w-20 text-center font-bold text-gray-800 border-gray-300 border rounded-md py-1 px-2" />
                <button @click="$emit('save-override')" class="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded-md hover:bg-blue-200 transition-colors">臨時調整</button>
              </div>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-500">已登錄休假：</span>
              <span class="font-bold text-orange-600">{{ activeCellSummary.leave }} 小時</span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-500">其他已排班：</span>
              <span class="font-bold text-blue-600">{{ activeCellSummary.scheduled }} 小時</span>
            </div>
            <div class="flex justify-between border-t border-gray-200 pt-1 mt-1">
              <span class="font-bold text-gray-800">尚可安排：</span>
              <span class="font-bold text-green-600 text-base">{{ activeCellSummary.available }} 小時</span>
            </div>
          </div>
        </div>

        <div class="flex space-x-3 mt-6">
          <button v-if="existingLeaveId" @click="$emit('remove-leave', existingLeaveId as number)" class="flex-1 bg-red-100 text-red-600 py-3 rounded-xl font-bold hover:bg-red-200 transition-colors">註銷休假</button>
          <button @click="$emit('submit-leave')" class="flex-1 bg-orange-500 text-white py-3 rounded-xl font-bold hover:bg-orange-600 shadow-md transition-colors">儲存休假</button>
        </div>
      </div>

      <div v-if="cellActionTab === 'shift'" class="space-y-4">
        <div v-if="isAdmin || isProducer">
          <label class="block text-sm font-bold text-gray-700 mb-2">更換負責人 (僅限同部門)</label>
          <select :value="newShift.staff_id ?? ''" @change="$emit('update:newShift', { ...props.newShift, staff_id: Number(($event.target as HTMLSelectElement).value) })" class="w-full border rounded-lg p-3 outline-none bg-gray-50 font-bold focus:ring-2 focus:ring-purple-500">
             <option v-for="s in staffOfSameDept" :key="s.id" :value="s.id">
               {{ s.name }}
             </option>
          </select>
        </div>

        <div>
          <label class="block text-sm font-bold text-gray-700 mb-2">指派節目</label>
          <select :value="newShift.program_id" @change="$emit('update:newShift', { ...props.newShift, program_id: ($event.target as HTMLSelectElement).value })" class="w-full border rounded-lg p-3 outline-none bg-gray-50 font-bold focus:ring-2 focus:ring-purple-500">
             <option disabled value="">請選擇節目...</option>
             <option v-for="p in programs" :key="p.id" :value="p.id">
               {{ p.name }} (目標總時數: {{ p.estimated_hours }}h)
             </option>
          </select>
          
          <div class="mt-2 p-3 bg-gray-50 rounded-lg border border-gray-200 text-sm">
            <h4 class="font-bold text-gray-600 mb-2">本日工時狀態</h4>
            <div class="space-y-1">
              <div v-if="isAdmin" class="flex justify-between items-center">
                <span class="text-gray-500">上班時數：</span>
                <div class="flex items-center gap-2">
                  <input type="number" step="0.5" :value="tempDailyLimit" @input="$emit('update:tempDailyLimit', Number(($event.target as HTMLInputElement).value))" class="w-20 text-center font-bold text-gray-800 border-gray-300 border rounded-md py-1 px-2" />
                  <button @click="$emit('save-override')" class="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded-md hover:bg-blue-200 transition-colors">臨時調整</button>
                </div>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">已登錄休假：</span>
                <span class="font-bold text-orange-600">{{ activeCellSummary.leave }} 小時</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">其他已排班：</span>
                <span class="font-bold text-blue-600">{{ activeCellSummary.scheduled }} 小時</span>
              </div>
              <div class="flex justify-between border-t border-gray-200 pt-1 mt-1">
                <span class="font-bold text-gray-800">尚可安排：</span>
                <span class="font-bold text-green-600 text-base">{{ activeCellSummary.available }} 小時</span>
              </div>
            </div>
          </div>
        </div>
        
        <div>
          <label class="block text-sm font-bold text-gray-700 mb-2">排班時數 (小時)</label>
          <input :value="newShift.duration" @input="$emit('update:newShift', { ...props.newShift, duration: Number(($event.target as HTMLInputElement).value) })" type="number" step="0.5" class="w-full border rounded-lg p-3 outline-none focus:ring-2 focus:ring-purple-500 font-bold bg-gray-50 text-center text-xl" />
        </div>

        <div class="flex space-x-3 mt-6">
          <button v-if="existingShiftId" @click="$emit('remove-shift', existingShiftId as number)" class="flex-1 bg-red-100 text-red-600 py-3 rounded-xl font-bold hover:bg-red-200 transition-colors">註銷排班</button>
          <button @click="$emit('submit-shift')" class="flex-1 bg-purple-600 text-white py-3 rounded-xl font-bold hover:bg-purple-700 shadow-md transition-colors">儲存排班</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useScheduleStore } from '../../stores/schedule'
import { storeToRefs } from 'pinia'
import { calculateHoursDiff } from '../../utils/timeUtils'

// 1. 從 Pinia 直接拿共用資料
const scheduleStore = useScheduleStore()
const { programs, staffList, workHoursOverrides, monthlyShifts, leaveMatrixMap } = storeToRefs(scheduleStore)

// 2. 定義從父元件 (AdminView) 接收的控制狀態 (TypeScript 版)
interface Props {
  show: boolean;
  isAdmin: boolean;
  isProducer: boolean;
  activeCell: { staff_id: number | null, date: string, staff_name: string };
  cellActionTab: string;
  newShift: {
    staff_id: number | null;
    program_id: string;
    department_id: number | null;
    duration: number;
    start_time: string;
    end_time: string;
  };
  newLeave: { staff_id: number | string; date: string; leave_type: string; hours: number };
  existingShiftId: number | null;
  existingLeaveId: number | null;
  tempDailyLimit: number;
  leaveTypes: string[] | undefined;
  staffOfSameDept: any[];
}

const props = withDefaults(defineProps<Props>(), {
  leaveTypes: () => ["特休", "例假日", "休假日", "補休", "病假", "事假"]
})

// 3. 定義要把操作傳回給父元件的事件
const emit = defineEmits<{
  (e: 'update:show', value: boolean): void;
  (e: 'update:cellActionTab', value: string): void;
  (e: 'update:newShift', value: any): void;
  (e: 'update:newLeave', value: any): void;
  (e: 'update:tempDailyLimit', value: number): void;
  (e: 'save-override'): void;
  (e: 'submit-leave'): void;
  (e: 'remove-leave', id: number): void;
  (e: 'submit-shift'): void;
  (e: 'remove-shift', id: number): void;
}>()

// 關閉彈窗的快捷方法
const closeModal = () => emit('update:show', false)

// 計算指定日期的工時摘要
const activeCellSummary = computed(() => {
  if (!props.show) {
    return { leave: '0', scheduled: '0', available: '8', daily_limit: '8', base_daily_limit: '8' };
  }

  const { staff_id, date } = props.activeCell;
  if (staff_id === null) return { leave: '0', scheduled: '0', available: '8', daily_limit: '8', base_daily_limit: '8' };

  // Check for override first
  const override = (workHoursOverrides.value as any[]).find((o: any) => o.staff_id === staff_id && o.date === date);

  let base_daily_limit = 8.0;
  if (override) {
    base_daily_limit = override.hours;
  } else {
    const staffMember = (staffList.value as any[]).find((s: any) => s.id === staff_id);
    if (staffMember) {
      base_daily_limit = staffMember.daily_work_hours;
    }
  }

  const effective_daily_limit = base_daily_limit - Math.floor(base_daily_limit / 9);
  const leave_hours = (leaveMatrixMap.value as any)[staff_id]?.[date]?.hours || 0;

  let other_gross_hours = 0;
  (monthlyShifts.value as any[]).forEach((shift: any) => {
    // 排除目前正在編輯的這筆班表 (如果是更新模式)
    if (shift.staff_id === staff_id && shift.date === date && shift.id !== props.existingShiftId) {
      other_gross_hours += calculateHoursDiff(shift.start_time, shift.end_time);
    }
  });

  // 修改：計算「尚可安排」時，不應預先扣除目前輸入框中的時數，否則新増時預設 8 小時會導致顯示 0
  const available_hours = effective_daily_limit - (leave_hours + other_gross_hours);

  return {
    leave: leave_hours.toFixed(1),
    scheduled: other_gross_hours.toFixed(1),
    available: Math.max(0, available_hours).toFixed(1),
    daily_limit: effective_daily_limit.toFixed(1),
    base_daily_limit: base_daily_limit.toFixed(1)
  };
});

</script>
