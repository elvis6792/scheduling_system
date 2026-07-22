// src/composables/useAiActions.ts
import { type Ref } from 'vue'
import api from '../api'
import { calculateHoursDiff } from '../utils/timeUtils'
import { useScheduleStore } from '../stores/schedule'
import { storeToRefs } from 'pinia'

// 定義需要從外部傳入的狀態
interface AiActionOptions {
  chatLog: Ref<any[]>;
  isLoading: Ref<boolean>;
  activeToolPayload: Ref<any>;
  showCancelAllModal: Ref<boolean>;
  showSwapModal: Ref<boolean>;
  showLeaveReallocateModal: Ref<boolean>;
  monthlyShifts: Ref<any[]>;
  fetchData: () => Promise<void>;
}

export function useAiActions(options: AiActionOptions) {
  const {
    chatLog,
    isLoading,
    activeToolPayload,
    showCancelAllModal,
    showSwapModal,
    showLeaveReallocateModal,
    monthlyShifts,
    fetchData
  } = options

  // 從 Pinia 取得全域資料
  const scheduleStore = useScheduleStore()
  const { departments, staffList, programs } = storeToRefs(scheduleStore)

  const executeCancelAll = async () => {
    try {
      isLoading.value = true;
      showCancelAllModal.value = false;
      const targetDeptKeyword = activeToolPayload.value.department_keyword || '';

      const targetShifts = monthlyShifts.value.filter(shift => {
        if (!targetDeptKeyword) return true;
        const dept = departments.value.find(d => d.id === shift.department_id);
        return dept && dept.name.includes(targetDeptKeyword);
      });

      if (targetShifts.length === 0) {
        chatLog.value.push({ sender: 'agent', text: `系統提示：找不到符合條件的班表可供註銷。` });
        return;
      }

      let successCount = 0;
      for (const shift of targetShifts) {
        await api.delete(`/shifts/${shift.id}`);
        successCount++;
      }
      chatLog.value.push({ sender: 'agent', text: `註銷完畢：已成功清除 ${successCount} 筆排班紀錄。` });
    } catch (error: any) {
      chatLog.value.push({ sender: 'agent', text: `註銷過程中斷：${error.message}` });
    } finally {
      await fetchData();
      isLoading.value = false;
    }
  };

  const executeSwap = async () => {
    try {
      isLoading.value = true;
      showSwapModal.value = false;
      const payload = activeToolPayload.value;

      const extractAllStrings = (obj: any): string[] => {
        let strings: string[] = [];
        for (const key in obj) {
          if (typeof obj[key] === 'string') strings.push(obj[key].trim());
          else if (typeof obj[key] === 'object' && obj[key] !== null) strings = strings.concat(extractAllStrings(obj[key]));
        }
        return strings;
      };
      const payloadValues = extractAllStrings(payload);

      const matchedStaff = staffList.value.filter(s =>
        payloadValues.some(val => val && (s.name.includes(val) || val.includes(s.name)))
      );

      if (matchedStaff.length < 2) {
        chatLog.value.push({
          sender: 'agent',
          text: `無法從指令中辨識出兩位明確的員工姓名。系統僅找到：${matchedStaff.map(m=>m.name).join(', ') || '無'}`
        });
        return;
      }

      const [staffA, staffB] = matchedStaff;
      const dateMatch = JSON.stringify(payload).match(/\d{4}-\d{2}-\d{2}/);
      const targetDate = dateMatch ? dateMatch[0] : '';

      if (!targetDate) {
        chatLog.value.push({ sender: 'agent', text: `缺少目標日期，無法執行自動換班。` });
        return;
      }

      const shiftA = monthlyShifts.value.find(s => s.staff_id === staffA.id && String(s.date).startsWith(targetDate));
      const shiftB = monthlyShifts.value.find(s => s.staff_id === staffB.id && String(s.date).startsWith(targetDate));

      if (!shiftA && !shiftB) {
        chatLog.value.push({ sender: 'agent', text: `${staffA.name} 與 ${staffB.name} 在 ${targetDate} 皆無排班，無班可換。` });
        return;
      }

      const buildUpdatePayload = (shift: any, newStaffId: number) => ({
        date: shift.date,
        duration: shift.duration || calculateHoursDiff(shift.start_time, shift.end_time),
        department_id: shift.department_id,
        staff_id: newStaffId,
        program_id: shift.program_id,
        notes: shift.notes || "AI 自動換班註記"
      });

      let actionLog = "";
      if (shiftA && shiftB) {
        await api.post('/shifts/swap', { shift_id_a: shiftA.id, shift_id_b: shiftB.id });
        actionLog = `已成功將 ${staffA.name} 與 ${staffB.name} 於 ${targetDate} 的排班同步互換。`;
      } else if (shiftA && !shiftB) {
        await api.put(`/shifts/${shiftA.id}`, buildUpdatePayload(shiftA, staffB.id));
        actionLog = `${staffB.name} 當日無班，已將 ${staffA.name} 的班表單向轉移給 ${staffB.name}。`;
      } else if (!shiftA && shiftB) {
        await api.put(`/shifts/${shiftB.id}`, buildUpdatePayload(shiftB, staffA.id));
        actionLog = `${staffA.name} 當日無班，已將 ${staffB.name} 的班表單向轉移給 ${staffA.name}。`;
      }
      chatLog.value.push({ sender: 'agent', text: actionLog });
    } catch (error: any) {
      chatLog.value.push({ sender: 'agent', text: `換班執行失敗：${error.response?.data?.detail || error.message}` });
    } finally {
      await fetchData();
      isLoading.value = false;
    }
  };

  const executeLeaveReallocate = async () => {
    try {
      isLoading.value = true;
      showLeaveReallocateModal.value = false;
      
      const staffKeyword = activeToolPayload.value.staff_keyword || '';
      const targetStaff = staffList.value.find(s => s.name.includes(staffKeyword));

      if (!targetStaff) {
        chatLog.value.push({ sender: 'agent', text: `錯誤：找不到名為 "${staffKeyword}" 的員工。` });
        return;
      }

      const targetDate = activeToolPayload.value.date;
      if (!targetDate) {
        chatLog.value.push({ sender: 'agent', text: `錯誤：未指定請假日期。` });
        return;
      }

      await api.post('/leaves', { staff_id: targetStaff.id, date: targetDate, leave_type: '特休', hours: 8.0 });
      chatLog.value.push({ sender: 'agent', text: `已成功為 ${targetStaff.name} 在 ${targetDate} 登錄特休。` });

      const shiftOnDay = monthlyShifts.value.find(s => s.staff_id === targetStaff.id && s.date === targetDate);
      if (shiftOnDay) {
        const program = programs.value.find(p => p.id === shiftOnDay.program_id);
        chatLog.value.push({
          sender: 'agent',
          text: `**警告：戰力出現缺口！**\n員工 ${targetStaff.name} 在 ${targetDate} 原本安排了 **${program ? program.name : '未知節目'}**，現已請假，請安排人力填補。`
        });
      }
    } catch (error: any) {
      chatLog.value.push({ sender: 'agent', text: `處理請假發生錯誤：${error.response?.data?.detail || error.message}` });
    } finally {
      await fetchData();
      isLoading.value = false;
    }
  };

  return {
    executeCancelAll,
    executeSwap,
    executeLeaveReallocate
  }
}