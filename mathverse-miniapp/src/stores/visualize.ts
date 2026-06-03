import Taro from '@tarojs/taro';
import { create } from 'zustand';
import { request } from '../services/api';

interface VizResult {
  ggb_commands: any[];
  ggb_script: string | null;
  has_image: boolean;
  summary: Record<string, any>;
}

interface VizStore {
  loading: boolean;
  result: VizResult | null;
  error: string;
  analyzePhoto: (question: string, stage: string) => Promise<void>;
  reset: () => void;
}

export const useVisualizeStore = create<VizStore>((set) => ({
  loading: false,
  result: null,
  error: '',

  analyzePhoto: async (question, stage) => {
    let filePath: string;
    try {
      const res = await Taro.chooseImage({ count: 1, sizeType: ['compressed'], sourceType: ['camera', 'album'] });
      filePath = res.tempFilePaths[0];
    } catch {
      return; // user cancelled
    }
    if (!filePath) return;
    set({ loading: true, result: null, error: '' });
    try {
      const base64 = Taro.getFileSystemManager().readFileSync(filePath, 'base64') as string;
      const data = await request<VizResult>('/api/solve/visualize', {
        method: 'POST',
        data: { image_base64: base64, question, stage },
      });
      set({ result: data, loading: false });
    } catch (e: any) {
      set({ loading: false, error: e?.message || '分析失败' });
    }
  },

  reset: () => set({ loading: false, result: null, error: '' }),
}));
