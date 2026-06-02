import Taro from '@tarojs/taro';
import { create } from 'zustand';
import { request, setTokens, loadTokens } from '../services/api';

interface UserInfo {
  id: string;
  nickname: string;
  avatar_url: string | null;
  current_stage: string;
  exam_mode: string | null;
  tier: string;
  streak_days: number;
}

interface UserStore {
  user: UserInfo | null;
  isLogin: boolean;
  isLoading: boolean;
  login: () => Promise<void>;
  sendSmsCode: (phone: string) => Promise<{ debugCode?: string }>;
  loginByPhone: (phone: string, code: string) => Promise<void>;
  fetchUser: () => Promise<void>;
  updateProfile: (data: { current_stage?: string; exam_mode?: string | null; nickname?: string }) => Promise<void>;
  switchStage: (stage: string) => void;
}

export const useUserStore = create<UserStore>((set) => ({
  user: null,
  isLogin: false,
  isLoading: true,

  login: async () => {
    try {
      const loginRes = await Taro.login();
      if (!loginRes.code) throw new Error('Login failed');
      const data = await request<{
        access_token: string;
        refresh_token: string;
        user: UserInfo;
      }>(`/api/auth/wechat/mp-login`, {
        method: 'POST',
        data: { code: loginRes.code },
        requireAuth: false,
      });
      setTokens(data.access_token, data.refresh_token);
      set({ user: data.user, isLogin: true, isLoading: false });
    } catch (err) {
      console.error('Login failed:', err);
      set({ isLoading: false });
    }
  },

  sendSmsCode: async (phone) => {
    const data = await request<{ sent: boolean; debug_code?: string }>(
      '/api/auth/sms/send',
      { method: 'POST', data: { phone }, requireAuth: false }
    );
    return { debugCode: data.debug_code };
  },

  loginByPhone: async (phone, code) => {
    const data = await request<{
      access_token: string;
      refresh_token: string;
      user: UserInfo;
    }>('/api/auth/sms/verify', {
      method: 'POST',
      data: { phone, code },
      requireAuth: false,
    });
    setTokens(data.access_token, data.refresh_token);
    set({ user: data.user, isLogin: true, isLoading: false });
  },

  fetchUser: async () => {
    try {
      loadTokens();
      const user = await request<UserInfo>('/api/auth/me');
      set({ user, isLogin: true, isLoading: false });
    } catch {
      set({ isLoading: false });
    }
  },

  updateProfile: async (data) => {
    const updated = await request<UserInfo>('/api/me/profile', { method: 'PATCH', data });
    set({ user: updated });
  },

  switchStage: (stage: string) => {
    set((s) => ({
      user: s.user ? { ...s.user, current_stage: stage } : null,
    }));
  },
}));
