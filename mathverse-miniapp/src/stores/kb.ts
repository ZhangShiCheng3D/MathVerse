import { create } from 'zustand';
import { request } from '../services/api';

export interface KbItem {
  name: string;
  read_only: boolean;
  shared: boolean;
  status: string | null;
  statistics: Record<string, any>;
}

interface KbStore {
  list: KbItem[];
  loading: boolean;
  busy: boolean;
  error: string;
  fetchList: () => Promise<void>;
  seedCurriculum: (stage: string) => Promise<void>;
  remove: (name: string) => Promise<void>;
}

export const useKbStore = create<KbStore>((set, get) => ({
  list: [],
  loading: false,
  busy: false,
  error: '',

  fetchList: async () => {
    set({ loading: true, error: '' });
    try {
      const d = await request<{ knowledge_bases: KbItem[] }>('/api/kb/list');
      set({ list: d.knowledge_bases || [], loading: false });
    } catch (e: any) {
      set({ loading: false, error: e?.message || '加载失败' });
    }
  },

  seedCurriculum: async (stage) => {
    set({ busy: true });
    try {
      await request(`/api/kb/curriculum/${stage}/seed`, { method: 'POST' });
      await get().fetchList();
    } finally {
      set({ busy: false });
    }
  },

  remove: async (name) => {
    set({ busy: true });
    try {
      await request(`/api/kb/${encodeURIComponent(name)}`, { method: 'DELETE' });
      await get().fetchList();
    } finally {
      set({ busy: false });
    }
  },
}));
