import { ref, computed, watch } from 'vue';
import api from '@/api';

export function useCalendar() {
  const today = new Date();
  const currentYear = ref(today.getFullYear());
  const currentMonth = ref(today.getMonth() + 1);
  const calendarDeptId = ref('');
  const unfilteredMonthlyShifts = ref([]);

  const monthlyShifts = computed(() => {
    if (!calendarDeptId.value) {
      return unfilteredMonthlyShifts.value;
    }
    return unfilteredMonthlyShifts.value.filter(s => s.department_id === calendarDeptId.value);
  });

  const fetchMonthlyShifts = async () => {
    try { 
      const res = await api.get('/shifts/month', { params: { year: currentYear.value, month: currentMonth.value } }); 
      unfilteredMonthlyShifts.value = res.data 
    } catch (e) { 
      console.error(e) 
    } 
  }

  watch([currentYear, currentMonth, calendarDeptId], () => { 
    fetchMonthlyShifts();
  }, { immediate: true });

  const getLocalDateString = (d) => {
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
  }

  const prevMonth = () => {
    if (currentMonth.value === 1) {
      currentMonth.value = 12;
      currentYear.value -= 1;
    } else {
      currentMonth.value -= 1;
    }
  }

  const nextMonth = () => {
    if (currentMonth.value === 12) {
      currentMonth.value = 1;
      currentYear.value += 1;
    } else {
      currentMonth.value += 1;
    }
  }

  const goToToday = () => {
    currentYear.value = today.getFullYear();
    currentMonth.value = today.getMonth() + 1;
  }

  const calendarDays = computed(() => {
    const days = []
    const firstDayOfMonth = new Date(currentYear.value, currentMonth.value - 1, 1)
    const lastDayOfMonth = new Date(currentYear.value, currentMonth.value, 0)
    const startDayOfWeek = firstDayOfMonth.getDay()
    
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

  return {
    currentYear,
    currentMonth,
    calendarDeptId,
    monthlyShifts,
    fetchMonthlyShifts,
    prevMonth,
    nextMonth,
    goToToday,
    calendarDays,
    unfilteredMonthlyShifts,
    today
  };
}
