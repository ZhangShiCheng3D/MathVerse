import { create } from 'zustand';
import { request } from '../services/api';

export interface Activity {
  id: string;
  title?: string;
  summary?: string;
  capability?: string;
  timestamp?: number;
  message_count?: number;
}

interface ActivityDetail {
  id: string;
  title?: string;
  content: { messages: { role: string; content: string }[]; summary?: string };
}

interface ActivityStore {
  list: Activity[];
  loading: boolean;
  error: string;
  detail: ActivityDetail | null;
  detailLoading: boolean;
  fetchRecent: () => Promise<void>;
  openEntry: (id: string) => Promise<void>;
  closeDetail: () => void;
}

export const useActivityStore = create<ActivityStore>((set) => ({
  list: [],
  loading: false,
  error: '',
  detail: null,
  detailLoading: false,

  fetchRecent: async () => {
    set({ loading: true, error: '' });
    try {
      const d = await request<{ activities: Activity[] }>('/api/activity/recent');
      set({ list: d.activities || [], loading: false });
    } catch (e: any) {
      set({ loading: false, error: e?.message || '加载失败' });
    }
  },

  openEntry: async (id) => {
    set({ detailLoading: true, detail: null });
    try {
      const d = await request<ActivityDetail>(`/api/activity/${encodeURIComponent(id)}`);
      set({ detail: d, detailLoading: false });
    } catch (e: any) {
      set({ detailLoading: false, error: e?.message || '读取失败' });
    }
  },

  closeDetail: () => set({ detail: null }),
}));
