<template>
  <transition name="apple-fade">
    <div v-if="showCancelAll || showSwap || showLeaveReallocate || showCoverage || showCreateShift" class="apple-overlay">
      
      <!-- 1. 註銷全月班表授權卡 (破壞性操作) -->
      <div v-if="showCancelAll" class="apple-modal destructive">
        <div class="modal-header">
          <h3>嚴重警告：註銷班表</h3>
        </div>
        <div class="modal-body">
          <p>系統準備執行全月班表註銷作業，請確認以下資訊：</p>
          <ul class="data-list">
            <li><strong>目標月份：</strong>{{ activeToolPayload?.month || '未指定' }}</li>
            <li><strong>目標部門：</strong>{{ activeToolPayload?.department_keyword || '全體' }}</li>
          </ul>
          <p class="warning-text">此操作將清除該月份所有相關排班，且無法復原。是否確認執行？</p>
        </div>
        <div class="modal-actions">
          <button class="apple-btn secondary" @click="$emit('update:showCancelAll', false)">取消</button>
          <button class="apple-btn danger" @click="$emit('execute-cancel-all')">確認註銷</button>
        </div>
      </div>

      <!-- 2. 換班作業授權卡 -->
      <div v-if="showSwap" class="apple-modal">
        <div class="modal-header">
          <h3>換班作業確認</h3>
        </div>
        <div class="modal-body">
          <p>系統準備執行換班作業：</p>
          <ul class="data-list">
            <li><strong>目標日期：</strong>{{ activeToolPayload?.date || '未指定' }}</li>
            <li><strong>涉及員工：</strong>{{ activeToolPayload?.staff_keyword || '未指定' }}</li>
          </ul>
          <p class="hint-text">按下確認後，將進入手動換班流程，請於後續介面選擇接替人選。</p>
        </div>
        <div class="modal-actions">
          <button class="apple-btn secondary" @click="$emit('update:showSwap', false)">取消</button>
          <button class="apple-btn primary" @click="$emit('execute-swap')">進入換班</button>
        </div>
      </div>

      <!-- 3. 請假與重新分配授權卡 -->
      <div v-if="showLeaveReallocate" class="apple-modal">
        <div class="modal-header">
          <h3>請假與戰力重分配</h3>
        </div>
        <div class="modal-body">
          <p>即將寫入假單並檢測空窗：</p>
          <ul class="data-list">
            <li><strong>申請人：</strong>{{ activeToolPayload?.staff_keyword || '未指定' }}</li>
            <li><strong>請假日期：</strong>{{ activeToolPayload?.date || '未指定' }}</li>
          </ul>
        </div>
        <div class="modal-actions">
          <button class="apple-btn secondary" @click="$emit('update:showLeaveReallocate', false)">取消</button>
          <button class="apple-btn primary" @click="$emit('execute-leave-reallocate')">確認寫入</button>
        </div>
      </div>

      <!-- 4. 戰力空窗分析報告卡 (資訊展示) -->
      <div v-if="showCoverage" class="apple-modal large">
        <div class="modal-header">
          <h3>戰力空窗分析報告</h3>
        </div>
        <div class="modal-body">
          <div class="analysis-meta">
            <span class="tag">期間：{{ activeToolPayload?.start_date }} 至 {{ activeToolPayload?.end_date }}</span>
            <span class="tag" v-if="activeToolPayload?.department_keyword">部門：{{ activeToolPayload?.department_keyword }}</span>
            <span class="tag" v-if="activeToolPayload?.staff_keyword">員工：{{ activeToolPayload?.staff_keyword }}</span>
          </div>
          
          <div class="analysis-content">
            <div class="table-container">
              <table class="apple-table">
                <thead>
                  <tr>
                    <th>員工姓名</th>
                    <th>已排班 (hr)</th>
                    <th>已請假 (hr)</th>
                    <th>剩餘額度 (hr)</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-if="coverageAnalysis.length === 0">
                    <td colspan="4" class="text-center text-gray-400">找不到符合條件的員工或資料。</td>
                  </tr>
                  <tr v-for="row in coverageAnalysis" :key="row.name">
                    <td>{{ row.name }}</td>
                    <td>{{ row.scheduled }}</td>
                    <td>{{ row.leave }}</td>
                    <td :class="{'text-danger font-bold': row.is_over_limit}">{{ row.available }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
        <div class="modal-actions centered">
          <button class="apple-btn primary" @click="$emit('update:showCoverage', false)">關閉報告</button>
        </div>
      </div>

      <!-- 5. 新增排班授權卡 -->
      <div v-if="showCreateShift" class="apple-modal">
        <div class="modal-header">
          <h3>AI 排班草案審查</h3>
        </div>
        <div class="modal-body">
          <p>{{ createShiftDisplay?.content || '系統準備執行排班作業：' }}</p>
          <ul class="data-list">
            <li><strong>日期：</strong>{{ createShiftPayload?.date || '未指定' }}</li>
            <li><strong>人員：</strong>{{ createShiftDisplay?.staff_name || '未指定' }}</li>
            <li><strong>節目：</strong>{{ createShiftDisplay?.prog_name || '未指定' }}</li>
            <li><strong>時間：</strong>{{ createShiftPayload?.start_time }}～{{ createShiftPayload?.end_time }}</li>
            <li v-if="createShiftPayload?.notes"><strong>備註：</strong>{{ createShiftPayload?.notes }}</li>
          </ul>
        </div>
        <div class="modal-actions">
          <button class="apple-btn secondary" @click="$emit('cancel-create-shift')">駁回</button>
          <button class="apple-btn primary" @click="$emit('execute-create-shift')">確認寫入</button>
        </div>
      </div>

    </div>
  </transition>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useScheduleStore } from '../../stores/schedule'
import { calculateHoursDiff } from '../../utils/timeUtils'

const scheduleStore = useScheduleStore()
const { departments, staffList, shiftMatrixMap, leaveMatrixMap } = storeToRefs(scheduleStore)

interface Props {
  showCancelAll: boolean;
  showSwap: boolean;
  showLeaveReallocate: boolean;
  showCoverage: boolean;
  showCreateShift: boolean;
  activeToolPayload: any;
  createShiftPayload: any;
  createShiftDisplay: any;
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'update:showCancelAll', value: boolean): void;
  (e: 'update:showSwap', value: boolean): void;
  (e: 'update:showLeaveReallocate', value: boolean): void;
  (e: 'update:showCoverage', value: boolean): void;
  (e: 'update:showCreateShift', value: boolean): void;
  (e: 'execute-cancel-all'): void;
  (e: 'execute-swap'): void;
  (e: 'execute-leave-reallocate'): void;
  (e: 'execute-create-shift'): void;
  (e: 'cancel-create-shift'): void;
}>()

const coverageAnalysis = computed(() => {
  const payload = props.activeToolPayload;
  if (!payload || !payload.start_date || !payload.end_date) return [];

  const start = new Date(payload.start_date);
  const end = new Date(payload.end_date);
  const deptKeyword = payload.department_keyword;
  const staffKeyword = payload.staff_keyword;

  const targetStaff = (staffList.value as any[]).filter(s =>
    (!deptKeyword || ((departments.value as any[]).find(d => d.id === s.department_id)?.name.includes(deptKeyword))) &&
    (!staffKeyword || s.name.includes(staffKeyword))
  );

  return targetStaff.map(staff => {
    let totalScheduled = 0, totalLeave = 0;
    const staffId = staff.id;

    for (const d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
      const dStr = d.toISOString().split('T')[0];
      const dayShifts = (shiftMatrixMap.value as any)[staffId]?.[dStr] || [];
      dayShifts.forEach((shift: any) => {
        totalScheduled += calculateHoursDiff(shift.start_time, shift.end_time);
      });

      const dayLeave = (leaveMatrixMap.value as any)[staffId]?.[dStr];
      if (dayLeave) {
        totalLeave += dayLeave.hours;
      }
    }
    const totalWorkableHours = ((end.getTime() - start.getTime()) / (1000 * 3600 * 24) + 1) * (staff.daily_work_hours || 8);
    const availableHours = totalWorkableHours - totalScheduled - totalLeave;
    return { name: staff.name, scheduled: totalScheduled.toFixed(1), leave: totalLeave.toFixed(1), available: availableHours.toFixed(1), is_over_limit: availableHours < 0 };
  });
});

</script>

<style scoped>
/* 將原本 AdminView.vue 最下方的 Apple 風格 CSS (.apple-overlay, .apple-modal 等) 全部剪下，貼到這裡 */
/* ========================================== */
/* Apple 風格彈窗樣式 */
/* ========================================== */
.apple-overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(4px);
}

.apple-modal {
  background-color: #f2f2f7;
  border-radius: 14px;
  width: 90%;
  max-width: 320px;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
  text-align: center;
  overflow: hidden;
}
.apple-modal.large { max-width: 520px; }

.modal-header { padding: 16px; }
.modal-header h3 {
  font-size: 17px;
  font-weight: 600;
  color: #000;
  margin: 0;
}

.modal-body {
  padding: 0 16px 16px;
  font-size: 13px;
  color: #333;
}
.modal-body p { margin: 4px 0 12px; }
.modal-body .warning-text { color: #d93025; font-weight: 500; }
.modal-body .hint-text { color: #5f6368; font-size: 12px; }

.data-list {
  list-style: none;
  padding: 8px 12px;
  margin: 12px 0;
  background-color: #fff;
  border-radius: 8px;
  text-align: left;
  border: 1px solid #e5e5e5;
}
.data-list li {
  padding: 6px 0;
  display: flex;
  justify-content: space-between;
  border-bottom: 1px solid #e5e5e5;
}
.data-list li:last-child { border-bottom: none; }
.data-list strong { color: #000; }

.modal-actions {
  display: flex;
  border-top: 1px solid #dcdce0;
}
.modal-actions.centered { justify-content: center; padding: 8px; }

.apple-btn {
  flex-grow: 1;
  background-color: transparent;
  border: none;
  padding: 12px;
  font-size: 17px;
  cursor: pointer;
  color: #007aff;
  transition: background-color 0.1s;
}
.apple-btn:first-child {
  border-right: 1px solid #dcdce0;
}
.apple-btn:active { background-color: #e5e5e5; }

.apple-btn.secondary { color: #007aff; }
.apple-btn.primary { font-weight: 600; }
.apple-btn.danger { color: #ff3b30; font-weight: 600; }

.apple-modal.destructive .modal-header h3 { color: #d93025; }

/* 報告分析卡 */
.analysis-meta { padding: 8px 0; display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; }
.analysis-meta .tag {
  background-color: #e8eaed;
  color: #3c4043;
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}
.analysis-content { max-height: 300px; overflow-y: auto; padding: 8px; background-color: #fff; border-radius: 8px; border: 1px solid #e5e5e5; }
.apple-table { width: 100%; border-collapse: collapse; }
.apple-table th, .apple-table td { padding: 10px; text-align: left; border-bottom: 1px solid #e5e5e5; }
.apple-table th { font-size: 12px; color: #5f6368; }
.apple-table td { font-size: 14px; }
.apple-table .text-danger { color: #ff3b30; }

.apple-fade-enter-active, .apple-fade-leave-active { transition: opacity 0.2s ease; }
.apple-fade-enter-from, .apple-fade-leave-to { opacity: 0; }
</style>