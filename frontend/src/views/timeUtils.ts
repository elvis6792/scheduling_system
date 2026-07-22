// 判斷是否為跨夜班 (結束時間小於開始時間)
export const isOvernight = (start: string, end: string): boolean => {
  if (!start || !end) return false;
  const [sH, sM] = start.split(':').map(Number);
  const [eH, eM] = end.split(':').map(Number);
  return (eH + eM / 60) < (sH + sM / 60);
};

// 終極版：精準計算兩個時間的時數差 (支援跨夜班)
export const calculateHoursDiff = (start: string | undefined, end: string | undefined): number => {
  if (!start || !end) return 0;

  // 為了相容不同格式，先確保只取 HH:MM
  const startStr = typeof start === 'string' ? start.slice(0, 5) : '';
  const endStr = typeof end === 'string' ? end.slice(0, 5) : '';

  if (!startStr || !endStr) return 0;

  const [sH, sM] = startStr.split(':').map(Number);
  const [eH, eM] = endStr.split(':').map(Number);

  let rawHours = (eH + eM / 60) - (sH + sM / 60);

  // 若為負數，代表跨越了午夜 00:00，需加上 24 小時
  if (rawHours < 0) {
    rawHours = 24 + rawHours;
  }

  return parseFloat(rawHours.toFixed(1));
};