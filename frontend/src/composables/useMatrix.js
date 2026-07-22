import { computed } from 'vue';

export function useMatrix(currentYear, currentMonth, monthlyShifts, leaves) {
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
    const map = {};
    monthlyShifts.value.forEach(shift => {
      if (!map[shift.staff_id]) {
        map[shift.staff_id] = {};
      }
      if (!map[shift.staff_id][shift.date]) {
        map[shift.staff_id][shift.date] = [];
      }
      map[shift.staff_id][shift.date].push(shift); 
    });
    return map;
  });

  const leaveMatrixMap = computed(() => {
    const map = {};
    leaves.value.forEach(l => {
      if (!map[l.staff_id]) map[l.staff_id] = {};
      map[l.staff_id][l.date] = l;
    });
    return map;
  });

  return {
    matrixDays,
    shiftMatrixMap,
    leaveMatrixMap
  };
}
