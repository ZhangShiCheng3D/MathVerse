import { create } from 'zustand';
import { request } from '../services/api';

export interface Book {
  id: string;
  title?: string;
  status?: string;
  [k: string]: any;
}

interface BookDetail {
  book: Book;
  pages: any[];
}

interface BookStore {
  list: Book[];
  loading: boolean;
  busy: boolean;
  error: string;
  detail: BookDetail | null;
  detailLoading: boolean;
  page: any | null;
  fetchList: () => Promise<void>;
  create: (intent: string) => Promise<string | null>;
  generate: (id: string) => Promise<void>;
  open: (id: string) => Promise<void>;
  openPage: (p: any) => void;
  closePage: () => void;
  closeDetail: () => void;
  remove: (id: string) => Promise<void>;
}

export const useBookStore = create<BookStore>((set, get) => ({
  list: [],
  loading: false,
  busy: false,
  error: '',
  detail: null,
  detailLoading: false,
  page: null,

  fetchList: async () => {
    set({ loading: true, error: '' });
    try {
      const d = await request<{ books: Book[] }>('/api/book/list');
      set({ list: d.books || [], loading: false });
    } catch (e: any) {
      set({ loading: false, error: e?.message || '加载失败' });
    }
  },

  create: async (intent) => {
    set({ busy: true });
    try {
      const d = await request<{ book_id: string }>('/api/book/create', {
        method: 'POST', data: { user_intent: intent },
      });
      await get().fetchList();
      return d.book_id || null;
    } finally {
      set({ busy: false });
    }
  },

  // 3-stage generation (proposal → spine → compile); can take a while.
  generate: async (id) => {
    set({ busy: true });
    try {
      await request(`/api/book/${encodeURIComponent(id)}/generate`, { method: 'POST' });
      await get().fetchList();
    } finally {
      set({ busy: false });
    }
  },

  open: async (id) => {
    set({ detailLoading: true, detail: null, page: null });
    try {
      const d = await request<{ book: Book; pages: any[] }>(`/api/book/${encodeURIComponent(id)}`);
      set({ detail: { book: d.book, pages: d.pages || [] }, detailLoading: false });
    } catch (e: any) {
      set({ detailLoading: false, error: e?.message || '读取失败' });
    }
  },

  openPage: (p) => set({ page: p }),
  closePage: () => set({ page: null }),
  closeDetail: () => set({ detail: null, page: null }),

  remove: async (id) => {
    set({ busy: true });
    try {
      await request(`/api/book/${encodeURIComponent(id)}`, { method: 'DELETE' });
      await get().fetchList();
    } finally {
      set({ busy: false });
    }
  },
}));
