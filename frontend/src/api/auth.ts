import { apiClient } from './client';
import { LoginPayload, RegisterPayload, TokenResponse, User } from '@/types/auth';

export async function loginUser(payload: LoginPayload): Promise<TokenResponse> {
  const response = await apiClient.post<TokenResponse>('/api/auth/login', payload);
  return response.data;
}

export async function registerUser(payload: RegisterPayload): Promise<User> {
  const response = await apiClient.post<User>('/api/auth/register', payload);
  return response.data;
}

export async function fetchCurrentUser(): Promise<User> {
  const response = await apiClient.get<User>('/api/auth/me');
  return response.data;
}
