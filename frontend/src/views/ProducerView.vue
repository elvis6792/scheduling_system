
<template>
  <div class="p-4 sm:p-6 md:p-8">
    <h1 class="text-3xl font-bold text-gray-800 mb-6">製作人排班介面 (Producer View)</h1>

    <form @submit.prevent="handleSearch" class="bg-white p-6 rounded-lg shadow-md mb-8">
      <div class="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-6">
        <div>
          <label for="date" class="block text-sm font-medium text-gray-700">日期 (Date)</label>
          <input
            type="date"
            id="date"
            v-model="searchParams.date"
            class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
            required
          />
        </div>
        <div>
          <label for="department" class="block text-sm font-medium text-gray-700">部門 (Department)</label>
          <select
            id="department"
            v-model="searchParams.department_id"
            class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
            required
          >
            <option v-for="dept in departments" :key="dept.id" :value="dept.id">
              {{ dept.name }}
            </option>
          </select>
        </div>
        <div>
          <label for="time_slot" class="block text-sm font-medium text-gray-700">時段 (Time Slot)</label>
          <select
            id="time_slot"
            v-model="searchParams.time_slot"
            class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
            required
          >
            <option v-for="slot in timeSlots" :key="slot" :value="slot">
              {{ slot }}
            </option>
          </select>
        </div>
        <div class="md:col-start-3 lg:col-start-4 flex items-end">
          <button
            type="submit"
            :disabled="isLoading"
            class="w-full inline-flex justify-center items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:bg-indigo-300 disabled:cursor-not-allowed"
          >
            <svg v-if="isLoading" class="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            {{ isLoading ? '搜尋中...' : '搜尋可排班人員 (Search)' }}
          </button>
        </div>
      </div>
    </form>

    <div>
      <h2 class="text-2xl font-semibold text-gray-700 mb-4">可排班人員 (Available Staff)</h2>
      
      <div v-if="isLoading" class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
        <div v-for="n in 10" :key="n" class="bg-white p-4 rounded-lg shadow animate-pulse">
          <div class="h-4 bg-gray-200 rounded w-3/4 mb-4"></div>
          <div class="h-8 bg-gray-300 rounded w-full"></div>
        </div>
      </div>

      <div v-else-if="availableStaff && availableStaff.length > 0" class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
        <div v-for="staff in availableStaff" :key="staff.id" class="bg-white p-4 rounded-lg shadow-md flex flex-col justify-between transition-transform transform hover:-translate-y-1">
          <span class="font-medium text-gray-800">{{ staff.name }}</span>
          <button
            @click="handleAssignShift(staff.id)"
            class="mt-3 w-full inline-flex justify-center rounded-md border border-transparent bg-green-500 px-3 py-1.5 text-sm font-medium text-white shadow-sm hover:bg-green-600 focus:outline-none focus:ring-2 focus:ring-green-400 focus:ring-offset-2"
          >
            排班 (Assign Shift)
          </button>
        </div>
      </div>
      
      <div v-else class="text-center py-10 px-4 bg-white rounded-lg shadow-md">
        <p class="text-gray-500">{{ hasSearched ? '沒有可用的排班人員 (No available staff found.)' : '請先執行搜尋 (Please perform a search to see results.)' }}</p>
      </div>
    </div>
  </div>
</template>



<script setup lang="ts">
import { ref, computed } from 'vue';
import { useToast } from 'vue-toastification';
import api from '@/api';
import type { Staff, ShiftCreate } from '@/types/openapi';

const toast = useToast();



const searchParams = ref({
  date: new Date().toISOString().split('T')[0],
  department_id: 1,
  time_slot: '早班',
});

const availableStaff = ref<Staff[] | null>(null);
const isLoading = ref(false);
const hasSearched = ref(false);



const departments = [
  { id: 1, name: '企劃部' },
  { id: 2, name: '製作部' },
  { id: 3, name: '攝影部' },
  { id: 4, name: '後製部' },
  { id: 5, name: '行政部' },
];

const timeSlots = ['早班', '晚班', '大夜班'];



const handleSearch = async () => {
  isLoading.value = true;
  hasSearched.value = true;
  availableStaff.value = [];

  try {
    const response = await api.get<Staff[]>('/producer/available-staff', {
      params: {
        date: searchParams.value.date,
        department_id: searchParams.value.department_id,
        time_slot: searchParams.value.time_slot,
      },
    });
    availableStaff.value = response.data;
  } catch (error) {
    console.error("Failed to fetch available staff:", error);
  } finally {
    isLoading.value = false;
  }
};

const handleAssignShift = async (staffId: number) => {
  const payload: ShiftCreate = {
    date: searchParams.value.date,
    time_slot: searchParams.value.time_slot,
    department_id: searchParams.value.department_id,
    staff_id: staffId,
  };

  try {
    await api.post('/producer/shifts', payload);
    
    toast.success(`成功為 ${availableStaff.value?.find(s => s.id === staffId)?.name} 排班`);
    
    if (availableStaff.value) {
      availableStaff.value = availableStaff.value.filter(staff => staff.id !== staffId);
    }
  } catch (error: any) {
    if (error.response && (error.response.status === 400 || error.response.status === 409)) {
      toast.error('該員已被排班 / Already scheduled');
      await handleSearch();
    } else {
      console.error("Failed to assign shift:", error);
    }
  }
};
</script>
