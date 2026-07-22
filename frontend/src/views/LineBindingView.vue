
<template>
  <div class="p-6 max-w-4xl mx-auto animate-fade-in">
    <div class="mb-8 border-b pb-4">
      <h2 class="text-3xl font-bold text-gray-800">LINE 通訊服務設定</h2>
      <p class="text-gray-500 mt-2">管理您與電視台排班小幫手的連動狀態，開啟零時差的數位應變通知。</p>
    </div>

    <div class="flex justify-center">
      <LineBinding />
    </div>
  </div>
</template>



<script setup>
import LineBinding from '@/components/LineBinding.vue'
</script>