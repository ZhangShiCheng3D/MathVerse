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
interface _Picked { name: string; path?: string; file?: any }

// weapp has Taro.chooseMessageFile (returns a tempfile path); h5/App has no Taro
// doc picker, so use a DOM <input type=file> (this branch is dropped from the
// weapp bundle since process.env.TARO_ENV is inlined at build time).
const _pickFile = async (): Promise<_Picked | null> => {
  if (process.env.TARO_ENV === 'weapp') {
    const chosen: any = await Taro.chooseMessageFile({ count: 1, type: 'file' });
    const f = chosen?.tempFiles?.[0];
    return f ? { name: f.name || 'doc', path: f.path } : null;
  }
  return new Promise((resolve) => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.pdf,.txt,.md,.markdown,.doc,.docx';
    input.onchange = () => {
      const file = input.files && input.files[0];
      resolve(file ? { name: file.name, file } : null);
    };
    input.click();
  });
};

const _upload = async (path: string, picked: _Picked, formData?: Record<string, any>) => {
  let token = '';
  try { token = Taro.getStorageSync('access_token') || ''; } catch { /* no token */ }
  const base = process.env.TARO_APP_API_URL || 'https://kuangyebar.cn';
  const auth: any = token ? { Authorization: `Bearer ${token}` } : {};
  if (picked.path) {
    // weapp: native upload from a tempfile path (filename carries the extension).
    const res: any = await Taro.uploadFile({
      url: `${base}${path}`, filePath: picked.path, name: 'files', formData, header: auth,
    });
    if (res.statusCode >= 400) {
      let detail = '上传失败';
      try { detail = JSON.parse(res.data)?.detail || detail; } catch { /* non-json */ }
      throw new Error(detail);
    }
    return;
  }
  // h5/App: fetch + FormData with the real File so the filename (+ extension,
  // which DeepTutor needs for file-type detection) is preserved.
  const fd = new FormData();
  fd.append('files', picked.file, picked.name);
  if (formData) Object.entries(formData).forEach(([k, v]) => fd.append(k, String(v)));
  const res = await fetch(`${base}${path}`, { method: 'POST', body: fd, headers: auth });
  if (!res.ok) {
    let detail = '上传失败';
    try { detail = (await res.json())?.detail || detail; } catch { /* non-json */ }
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
    set({ busy: true, error: '' });
    try {
      const picked = await _pickFile();
      if (!picked) return;
      const kbName = (picked.name.replace(/\.[^.]+$/, '').slice(0, 40)) || '我的资料';
      await _upload('/api/kb/create', picked, { name: kbName });
      await get().fetchList();
    } catch (e: any) {
      set({ error: e?.message || '上传失败' });
    } finally {
      set({ busy: false });
    }
  },

  uploadDoc: async (name) => {
    set({ busy: true, error: '' });
    try {
      const picked = await _pickFile();
      if (!picked) return;
      await _upload(`/api/kb/${encodeURIComponent(name)}/upload`, picked);
      await get().fetchList();
    } catch (e: any) {
      set({ error: e?.message || '上传失败' });
    } finally {
      set({ busy: false });
    }
  },
}));
