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
  fetchUser: () => Promise<void>;
  switchStage: (stage: string) => void;
}

export const useUserStore = create<UserStore>((set, get) => ({
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

  fetchUser: async () => {
    try {
      loadTokens();
      const user = await request<UserInfo>('/api/auth/me');
      set({ user, isLogin: true, isLoading: false });
    } catch {
      set({ isLoading: false });
    }
  },

  switchStage: (stage: string) => {
    set((s) => ({
      user: s.user ? { ...s.user, current_stage: stage } : null,
    }));
  },
}));
