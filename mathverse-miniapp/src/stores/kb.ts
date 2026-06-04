import Taro from '@tarojs/taro';
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
  createWithDoc: () => Promise<void>;
  uploadDoc: (name: string) => Promise<void>;
}

// Document upload uses multipart (Taro.uploadFile), which the JSON `request()`
// helper can't do. Taro has no cross-platform document picker — chooseMessageFile
// is weapp-only — so h5/App is gated with a message until a DOM-input path lands.
const _pickFile = async (): Promise<{ path: string; name: string } | null> => {
  const chosen: any = await Taro.chooseMessageFile({ count: 1, type: 'file' });
  const f = chosen?.tempFiles?.[0];
  return f ? { path: f.path, name: f.name || 'doc' } : null;
};

const _upload = async (path: string, filePath: string, formData?: Record<string, any>) => {
  let token = '';
  try { token = Taro.getStorageSync('access_token') || ''; } catch { /* no token */ }
  const base = process.env.TARO_APP_API_URL || 'https://kuangyebar.cn';
  const res: any = await Taro.uploadFile({
    url: `${base}${path}`,
    filePath,
    name: 'files',
    formData,
    header: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (res.statusCode >= 400) {
    let detail = '上传失败';
    try { detail = JSON.parse(res.data)?.detail || detail; } catch { /* non-json */ }
    throw new Error(detail);
  }
};

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

  createWithDoc: async () => {
    if (process.env.TARO_ENV !== 'weapp') {
      set({ error: 'H5/App 端文档上传即将支持，请在微信小程序内上传' });
      return;
    }
    set({ busy: true, error: '' });
    try {
      const f = await _pickFile();
      if (!f) return;
      const kbName = (f.name.replace(/\.[^.]+$/, '').slice(0, 40)) || '我的资料';
      await _upload('/api/kb/create', f.path, { name: kbName });
      await get().fetchList();
    } catch (e: any) {
      set({ error: e?.message || '上传失败' });
    } finally {
      set({ busy: false });
    }
  },

  uploadDoc: async (name) => {
    if (process.env.TARO_ENV !== 'weapp') {
      set({ error: 'H5/App 端文档上传即将支持，请在微信小程序内上传' });
      return;
    }
    set({ busy: true, error: '' });
    try {
      const f = await _pickFile();
      if (!f) return;
      await _upload(`/api/kb/${encodeURIComponent(name)}/upload`, f.path);
      await get().fetchList();
    } catch (e: any) {
      set({ error: e?.message || '上传失败' });
    } finally {
      set({ busy: false });
    }
  },
}));
