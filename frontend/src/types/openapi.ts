
export interface LoginRequest {
  username: string;
  password: string;
}



export interface TokenResponse {
  access_token: string;
  token_type: string;
  role: "ADMIN" | "PRODUCER";
}



export interface Staff {
  id: number;
  name: string;
  department_id: number;
}



export interface Shift {
  id: number;
  date: string;
  time_slot: string;
  department_id: number;
  staff_id: number;
  created_by_user_id: number;
}



export interface ShiftCreate {
  date: string;
  time_slot: string;
  department_id: number;
  staff_id: number;
}



export interface HTTPValidationError {
  detail?: string;
}
