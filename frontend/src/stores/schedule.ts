import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/api'
import { useToast } from 'vue-toastification'
import axios from 'axios'

export const useScheduleStore = defineStore('schedule', () => {
  const toast = useToast()
  
  // --- 1. 時間狀態 (全域共用) ---
  const today = new Date()
  const currentYear = ref(today.getFullYear())
  const currentMonth = ref(today.getMonth() + 1)

  // --- 2. 核心資料陣列 ---
  const departments = ref<any[]>([])
  const staffList = ref<any[]>([])
  const programs = ref<any[]>([])
  const workHoursOverrides = ref<any[]>([])
  const leaves = ref<any[]>([])
  const users = ref<any[]>([])
  const monthlyShifts = ref<any[]>([])

  // --- 3. UI 狀態 ---
  const calendarDeptId = ref('')

  const fetchAllData = async (userRole: string) => {
    try {
      const firstDay = new Date(currentYear.value, currentMonth.value - 1, 1)
      const lastDay = new Date(currentYear.value, currentMonth.value, 0)

      const [dRes, sRes, pRes, oRes, mRes] = await Promise.all([
        api.get('/departments'),
        api.get('/staff'),
        api.get('/programs'),
        api.get('/work-hours-override', {
          params: {
            start_date: firstDay.toISOString().split('T')[0],
            end_date: lastDay.toISOString().split('T')[0]
          }
        }),
        api.get('/shifts/month', { params: { year: currentYear.value, month: currentMonth.value } })
      ])
      
      departments.value = dRes.data
      staffList.value = sRes.data
      programs.value = pRes.data
      workHoursOverrides.value = oRes.data
      monthlyShifts.value = mRes.data

      if (userRole === 'admin' || userRole === 'producer') {
        try {
          const uRes = await api.get('/users')
          users.value = uRes.data
        } catch (e) {
          console.warn("獲取帳號清單失敗", e)
        }
      }

      const lRes = await api.get('/leaves')
      leaves.value = lRes.data.sort((a: any, b: any) => new Date(b.date).getTime() - new Date(a.date).getTime())

    } catch (error: any) {
      console.error("資料載入失敗：", error)
      if (error.response && error.response.status === 401) {
        toast.error("憑證已失效，請重新登入！")
      }
    }
  }

  // --- 4. AI Agent 相關 ---
  const userInput = ref('')
  const chatLog = ref<any[]>([
    { sender: 'agent', text: '您好，我是 AI 排班助理。您可以吩咐我建立排班、修改班表（換人、換時間）、查詢空班，或取消班表喔！' }
  ])
  const isLoading = ref(false)
  const agentRequestController = ref<AbortController | null>(null)

  const clearChat = () => {
    chatLog.value = [{ sender: 'agent', text: '您好，我是 AI 排班助理。您可以吩咐我建立排班、修改班表（換人、換時間）、查詢空班，或取消班表喔！' }];
    toast.info("對話已清除");
  }

  const cancelAgentRequest = () => {
    if (agentRequestController.value) {
      agentRequestController.value.abort();
    }
  }

  const sendToAgent = async (userRole: string, handlers: any) => {
    if (!userInput.value.trim() || isLoading.value) return;

    agentRequestController.value = new AbortController();
    const currentInput = userInput.value;
    chatLog.value.push({ sender: 'user', text: currentInput });
    userInput.value = '';
    isLoading.value = true;

    try {
      const recentHistory = chatLog.value
        .slice(-7, -1)
        .filter(log => typeof log.text === 'string' && !log.text.includes('系統已解析指令'))
        .map(log => ({
          role: log.sender === 'user' ? 'user' : 'assistant',
          content: log.text
        }));

      const res = await api.post('/agent/chat', {
        message: currentInput,
        history: recentHistory
      }, {
        timeout: 120000,
        signal: agentRequestController.value.signal
      });

      if (res.data.type === 'tool_call') {
        const toolData = res.data.tool_data;
        const action = toolData.action;
        if (handlers[action]) {
          handlers[action](toolData);
        } else {
          chatLog.value.push({ sender: 'agent', text: "系統提示：AI 請求執行一個尚未定義的動作。" });
        }
      } else {
        // 確保後端回傳的 reply 有內容才推入
        const replyText = res.data.reply || res.data.message || "AI 目前無法回答，請稍後再試。";
        chatLog.value.push({ sender: 'agent', text: replyText });
      }
    } catch (err: any) {
      let errorMsg = '發生未知錯誤，請檢查系統日誌。';
      if (axios.isCancel(err)) {
        errorMsg = '您已手動中斷 AI 的思考。';
      } else if (err.code === 'ECONNABORTED' || err.message.includes('timeout')) {
        errorMsg = 'AI 運算超時，請查看後端終端機負載。';
      } else if (err.response?.data?.detail) {
        errorMsg = err.response.data.detail;
      } else if (err.message) {
        errorMsg = err.message;
      }
      chatLog.value.push({ sender: 'agent', text: `系統提示：${errorMsg}` });
    } finally {
      isLoading.value = false;
      agentRequestController.value = null;
    }
  }

  // --- 5. 日曆計算邏輯 (CalendarTab 用) ---
  const calendarDays = computed(() => {
    const days = []
    const firstDayOfMonth = new Date(currentYear.value, currentMonth.value - 1, 1)
    const lastDayOfMonth = new Date(currentYear.value, currentMonth.value, 0)
    const startDayOfWeek = firstDayOfMonth.getDay()

    const getLocalDateString = (d: Date) => {
      const yyyy = d.getFullYear();
      const mm = String(d.getMonth() + 1).padStart(2, '0');
      const dd = String(d.getDate()).padStart(2, '0');
      return `${yyyy}-${mm}-${dd}`;
    }

    for (let i = startDayOfWeek - 1; i >= 0; i--) {
      const d = new Date(currentYear.value, currentMonth.value - 1, -i);
      days.push({ date: getLocalDateString(d), dayNumber: d.getDate(), isCurrentMonth: false, isToday: false })
    }

    for (let i = 1; i <= lastDayOfMonth.getDate(); i++) {
      const d = new Date(currentYear.value, currentMonth.value - 1, i);
      const isToday = (d.getFullYear() === today.getFullYear() && d.getMonth() === today.getMonth() && d.getDate() === today.getDate());
      days.push({ date: getLocalDateString(d), dayNumber: i, isCurrentMonth: true, isToday: isToday })
    }

    const remainingCells = 7 - (days.length % 7)
    if (remainingCells < 7) {
      for (let i = 1; i <= remainingCells; i++) {
        const d = new Date(currentYear.value, currentMonth.value, i);
        days.push({ date: getLocalDateString(d), dayNumber: d.getDate(), isCurrentMonth: false, isToday: false })
      }
    }
    return days
  })

  // --- 6. 矩陣計算邏輯 (MatrixTab 用) ---
  const matrixDays = computed(() => {
    const days = [];
    const lastDay = new Date(currentYear.value, currentMonth.value, 0).getDate();
    const weekdays = ['日', '一', '二', '三', '四', '五', '六'];
    for (let i = 1; i <= lastDay; i++) {
      const d = new Date(currentYear.value, currentMonth.value - 1, i);
      const dateStr = `${currentYear.value}-${String(currentMonth.value).padStart(2, '0')}-${String(i).padStart(2, '0')}`;
      const dayOfWeek = d.getDay();
      days.push({
        day: i,
        dateStr: dateStr,
        weekdayStr: weekdays[dayOfWeek],
        isWeekend: dayOfWeek === 0 || dayOfWeek === 6
      });
    }
    return days;
  });

  const shiftMatrixMap = computed(() => {
    const map: any = {};
    monthlyShifts.value.forEach(shift => {
      if (!map[shift.staff_id]) map[shift.staff_id] = {};
      if (!map[shift.staff_id][shift.date]) map[shift.staff_id][shift.date] = [];
      map[shift.staff_id][shift.date].push(shift);
    });
    return map;
  });

  const leaveMatrixMap = computed(() => {
    const map: any = {};
    leaves.value.forEach(l => {
      if (!map[l.staff_id]) map[l.staff_id] = {};
      map[l.staff_id][l.date] = l;
    });
    return map;
  });

  const workHoursMatrixMap = computed(() => {
    const map: any = {};
    workHoursOverrides.value.forEach(o => {
      if (!map[o.staff_id]) map[o.staff_id] = {};
      map[o.staff_id][o.date] = o.hours;
    });
    return map;
  });

  return {
    currentYear, currentMonth,
    departments, staffList, programs, workHoursOverrides, leaves, users, monthlyShifts,
    calendarDeptId, calendarDays,
    matrixDays, shiftMatrixMap, leaveMatrixMap, workHoursMatrixMap,
    userInput, chatLog, isLoading,
    fetchAllData, clearChat, cancelAgentRequest, sendToAgent
  }
})
