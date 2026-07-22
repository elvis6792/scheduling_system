/// <reference types="vite/client" />
import axios from 'axios'
import { useAuthStore } from '../stores/auth'
import { useToast } from 'vue-toastification'

const toast = useToast()


const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1',
  timeout: 60000,
})


api.interceptors.request.use((config) => {
  const authStore = useAuthStore()
  const token = authStore.token

  if (token && config.headers && !config.headers.Authorization) {
    config.headers.Authorization = `Bearer ${token}`
  }

  return config
})


// 定義擴充的錯誤類型
interface ApiError extends Error {
  isCanceledByUser?: boolean;
  formattedMessage?: string;
  response?: {
    status: number;
    data: any;
  };
  config?: any;
}

api.interceptors.response.use(
  (response) => response,
  (error: any) => {
    const apiError = error as ApiError;

    if (axios.isCancel(error)) {
      apiError.isCanceledByUser = true;
      apiError.formattedMessage = '已中斷對話';
      return Promise.reject(apiError);
    }
    
    const authStore = useAuthStore()
    
    let errorMessage = '系統發生未知網路錯誤';
    
    if (error.response && error.response.data) {
      const detail = error.response.data.detail;
      
      if (typeof detail === 'string') {
        errorMessage = detail;
      } else if (Array.isArray(detail)) {
        errorMessage = detail.map((e: any) => e.msg).join(', ');
      } else {
        errorMessage = JSON.stringify(error.response.data);
      }
    } else if (error.message) {
      errorMessage = error.message;
    }

    apiError.formattedMessage = errorMessage;

    if (error.response) {
      const { status, data } = error.response

      if (status === 401) {
        authStore.clearToken()
        toast.error('登入逾時或權限失效，請重新登入')
      } else if (status === 400) {
        toast.error(data.detail || '請求錯誤')
      } else if (status === 403) {
        toast.error(data.detail || '您沒有權限執行此操作')
      } else if (status >= 500) {
        toast.error('伺服器發生錯誤，請稍後再試')
      }
    } else {
      toast.error('無法連線到伺服器')
    }

    return Promise.reject(error)
  }
)

export default api
