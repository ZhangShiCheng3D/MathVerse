import { create } from 'zustand';
import { request } from '../services/api';

export interface Notebook {
  id: string;
  name?: string;
  [k: string]: any;
}

interface NotebookStore {
  list: Notebook[];
  loading: boolean;
  busy: boolean;
  error: string;
  fetchList: () => Promise<void>;
  create: (name: string) => Promise<void>;
  remove: (id: string) => Promise<void>;
  addNote: (id: string, title: string, content: string) => Promise<void>;
}

export const useNotebookStore = create<NotebookStore>((set, get) => ({
  list: [],
  loading: false,
  busy: false,
  error: '',

  fetchList: async () => {
    set({ loading: true, error: '' });
    try {
      const d = await request<{ notebooks: Notebook[] }>('/api/notebook/list');
      set({ list: d.notebooks || [], loading: false });
    } catch (e: any) {
      set({ loading: false, error: e?.message || '加载失败' });
    }
  },

  create: async (name) => {
    set({ busy: true });
    try {
      await request('/api/notebook/create', { method: 'POST', data: { name } });
      await get().fetchList();
    } finally {
      set({ busy: false });
    }
  },

  remove: async (id) => {
    set({ busy: true });
    try {
      await request(`/api/notebook/${encodeURIComponent(id)}`, { method: 'DELETE' });
      await get().fetchList();
    } finally {
      set({ busy: false });
    }
  },

  // Used by "save to notebook" integrations (e.g. from a solve/tutor result).
  addNote: async (id, title, content) => {
    await request(`/api/notebook/${encodeURIComponent(id)}/record`, {
      method: 'POST',
      data: { title, user_query: title, output: content, record_type: 'chat' },
    });
  },
}));
