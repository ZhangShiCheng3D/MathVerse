import { create } from 'zustand';
import { request } from '../services/api';

export interface MemoryDoc {
  layer: string;
  key: string;
  [k: string]: any;
}

interface MemoryStore {
  docs: MemoryDoc[];
  loading: boolean;
  disabled: boolean;
  error: string;
  content: string | null;
  contentTitle: string;
  fetchOverview: () => Promise<void>;
  openDoc: (layer: string, key: string) => Promise<void>;
  closeDoc: () => void;
}

export const useMemoryStore = create<MemoryStore>((set) => ({
  docs: [],
  loading: false,
  disabled: false,
  error: '',
  content: null,
  contentTitle: '',

  fetchOverview: async () => {
    set({ loading: true, error: '', disabled: false });
    try {
      const d = await request<{ docs: MemoryDoc[] }>('/api/memory/overview');
      set({ docs: d.docs || [], loading: false });
    } catch (e: any) {
      const msg = e?.message || '';
      // 403 → operator hasn't enabled the (shared, read-only) memory inspector.
      if (msg.includes('未启用')) set({ disabled: true, loading: false });
      else set({ error: msg || '加载失败', loading: false });
    }
  },

  openDoc: async (layer, key) => {
    set({ content: null, contentTitle: `${layer} / ${key}` });
    try {
      const d = await request<{ content: string }>(`/api/memory/doc/${layer}/${encodeURIComponent(key)}`);
      set({ content: d.content || '（空）' });
    } catch (e: any) {
      set({ content: `读取失败：${e?.message || ''}` });
    }
  },

  closeDoc: () => set({ content: null, contentTitle: '' }),
}));
