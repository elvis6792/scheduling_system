<template>
  <div class="grid grid-cols-1 lg:grid-cols-3 gap-8 animate-fade-in">
    <div class="lg:col-span-3 bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex flex-col h-[600px]">
      
      <div class="flex justify-between items-center mb-4 border-b pb-2">
        <h2 class="text-xl font-bold text-gray-800">AI排班對話</h2>
        <button @click="$emit('clear-chat')" class="text-sm bg-gray-50 hover:bg-red-50 hover:text-red-600 text-gray-500 px-3 py-1.5 rounded-lg transition-colors flex items-center border border-gray-100">
          <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
          清除對話
        </button>
      </div>
      
      <div class="flex-1 p-6 overflow-y-auto space-y-4 bg-gray-50 rounded-xl custom-scrollbar" id="chat-box" ref="chatContainer">
        <div v-for="(chat, index) in chatLog" :key="index" :class="chat.sender === 'user' ? 'justify-end' : 'justify-start'" class="flex">
          <div :class="chat.sender === 'user' ? 'bg-purple-600 text-white rounded-br-none' : 'bg-white border text-gray-800 rounded-bl-none shadow-sm'" class="max-w-[70%] p-3.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap">
            {{ chat.text }}
          </div>
        </div>

        <div v-if="isLoading" class="justify-start flex animate-pulse">
          <div class="bg-white border text-gray-500 rounded-bl-none shadow-sm max-w-[70%] p-3.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap italic">
            思考中.....
          </div>
        </div>
      </div>

      <div class="mt-4 flex space-x-3 items-center">
        <textarea 
          :value="userInput" 
          @input="$emit('update:userInput', $event.target.value)"
          @keydown="handleKeyDown" 
          placeholder="輸入排班指令..." 
          class="flex-1 border border-gray-300 rounded-xl p-3 outline-none focus:ring-2 focus:ring-purple-500 transition-shadow text-sm resize-none" 
          rows="1" 
          :disabled="isLoading"
        ></textarea>
        <button v-if="!isLoading" @click="$emit('send-message')" class="bg-purple-600 text-white px-6 py-3 rounded-xl hover:bg-purple-700 font-bold transition-colors text-sm shadow-sm">
          對話
        </button>
        <button v-else @click="$emit('cancel-request')" class="bg-red-600 text-white px-6 py-3 rounded-xl hover:bg-red-700 font-bold transition-colors text-sm shadow-sm flex items-center">
          <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
          停止
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'

const props = defineProps({
  chatLog: {
    type: Array,
    required: true
  },
  isLoading: {
    type: Boolean,
    required: true
  },
  userInput: {
    type: String,
    required: true
  }
})

const emit = defineEmits(['update:userInput', 'send-message', 'clear-chat', 'cancel-request'])

const chatContainer = ref(null);

const scrollToBottom = async () => {
  await nextTick();
  if (chatContainer.value) {
    chatContainer.value.scrollTo({
      top: chatContainer.value.scrollHeight,
      behavior: 'smooth'
    });
  }
};

watch(() => props.chatLog, () => {
  scrollToBottom();
}, { deep: true });

const handleKeyDown = (e) => {
  if (e.isComposing || e.keyCode === 229) return;
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    emit('send-message');
  }
};

</script>
