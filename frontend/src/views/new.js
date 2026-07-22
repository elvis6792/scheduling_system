// 修正後的 getStaffByDept：不再限制只顯示自己
const getStaffByDept = (deptId) => {
  return staffList.value.filter(s => s.department_id === deptId)
}

// 修正後的模板判斷 (String 轉型比較)
:class="[
  // ... 其他類別
  userRole === 'staff' && String(staff.id) !== String(currentStaffId) 
    ? 'cursor-not-allowed hover:bg-gray-100 opacity-60 grayscale' 
    : 'cursor-pointer hover:bg-orange-100'
]"