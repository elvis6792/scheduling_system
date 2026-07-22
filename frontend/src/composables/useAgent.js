import { ref } from 'vue';
import axios from 'axios';
import api from '@/api';

export function useAgent(toast, showConfirm, actionHandlers) {
  const userInput = ref('');
  const chatLog = ref([]);
  const isLoading = ref(false);
  const agentRequestController = ref(null);

  if (chatLog.value.length === 0) {
    chatLog.value.push({
      sender: 'agent',
      text: '您好，我是 AI 排班助理。您可以吩咐我建立排班、修改班表（換人、換時間）、查詢空班，或取消班表喔！'
    });
  }

  const clearChat = () => {
    chatLog.value = [{ 
      sender: 'agent', 
      text: '您好，我是 AI 排班助理。您可以吩咐我建立排班、修改班表（換人、換時間）、查詢空班，或取消班表喔！' 
    }];
    toast.info("對話已清除");
  };

  const cancelAgentRequest = () => {
    if (agentRequestController.value) {
      agentRequestController.value.abort();
    }
  };

  const sendToAgent = async () => {
    if (!userInput.value.trim() || isLoading.value) {
      return;
    }

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
        
        if (actionHandlers[action]) {
            actionHandlers[action](toolData);
        } else {
            chatLog.value.push({ sender: 'agent', text: `錯誤：無法處理的動作 '${action}'` });
        }

      } else {
        chatLog.value.push({ sender: 'agent', text: res.data.reply });
      }
    } catch (err) {
      let errorMsg = '發生未知錯誤，請檢查系統日誌。';
      if (axios.isCancel(err)) {
        errorMsg = '您已手動中斷 AI 的思考。';
      } else if (err.code === 'ECONNABORTED' || err.message.includes('timeout')) {
        errorMsg = 'AI 運算超時，請查看後端終端機負載。';
      } else if (err.response && err.response.data && err.response.data.detail) {
        errorMsg = err.response.data.detail;
      } else if (err.message) {
        errorMsg = err.message;
      }
      chatLog.value.push({ sender: 'agent', text: `系統提示：${errorMsg}` });
    } finally {
      isLoading.value = false;
      agentRequestController.value = null;
    }
  };

  return {
    userInput,
    chatLog,
    isLoading,
    sendToAgent,
    clearChat,
    cancelAgentRequest,
  };
}
