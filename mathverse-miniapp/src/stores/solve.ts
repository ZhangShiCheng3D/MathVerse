import Taro from '@tarojs/taro';
import { create } from 'zustand';
import { request } from '../services/api';

interface SolveStep {
  index: number;
  title: string;
  content: string;
  why: string;
}

interface SolveResult {
  answer: string;
  steps: SolveStep[];
  knowledge_points: string[];
  related_topics: string[];
  common_mistakes: string[];
}

interface SolveStore {
  question: string;
  isSolving: boolean;
  result: SolveResult | null;
  expandedLayer: 1 | 2 | 3;
  expandedStepIndex: number | null;
  whyExplanation: string;
  isWhyLoading: boolean;
  addedToMistakes: boolean;
  streamingText: string;
  isStreaming: boolean;
  setQuestion: (q: string) => void;
  solve: (stage: string) => Promise<void>;
  solveStreaming: (stage: string) => Promise<void>;
  solveByPhoto: (stage: string) => Promise<void>;
  expandLayer: (layer: 1 | 2 | 3) => void;
  askWhy: (stepIndex: number, stepContent: string) => Promise<void>;
  addToMistakes: () => Promise<void>;
  reset: () => void;
}

export const useSolveStore = create<SolveStore>((set, get) => ({
  question: '',
  isSolving: false,
  result: null,
  expandedLayer: 1,
  expandedStepIndex: null,
  whyExplanation: '',
  isWhyLoading: false,
  addedToMistakes: false,
  streamingText: '',
  isStreaming: false,

  setQuestion: (q) => set({ question: q }),

  solveStreaming: async (stage) => {
    const { question } = get();
    if (!question.trim()) return;
    set({ isSolving: true, result: null, streamingText: '', isStreaming: true, addedToMistakes: false });

    const base = process.env.TARO_APP_API_URL || 'https://kuangyebar.cn';
    const wsUrl = base.replace(/^http/, 'ws') + '/ws/solve';
    let token = '';
    try { token = Taro.getStorageSync('access_token') || ''; } catch { /* no token */ }

    return new Promise<void>((resolve, reject) => {
      let settled = false;

      // Transport failure → transparently fall back to the POST path.
      const fallback = () => {
        if (settled) return;
        settled = true;
        set({ isStreaming: false });
        get().solve(stage).then(resolve).catch(reject);
      };

      (async () => {
        let task: any;
        try {
          // h5 returns a Promise<SocketTask>; weapp returns a SocketTask directly.
          task = Taro.connectSocket({ url: wsUrl });
          if (task && typeof task.then === 'function') task = await task;
        } catch {
          fallback();
          return;
        }
        if (!task || typeof task.onMessage !== 'function') {
          fallback();
          return;
        }

        task.onOpen(() => task.send({ data: JSON.stringify({ question, stage, token }) }));

        task.onMessage((res: any) => {
          let ev: any;
          try { ev = JSON.parse(res.data); } catch { return; }
          if (ev.type === 'chunk') {
            set((s) => ({ streamingText: s.streamingText + (ev.content || '') }));
          } else if (ev.type === 'result') {
            settled = true;
            set({
              result: {
                answer: ev.answer,
                steps: ev.steps || [],
                knowledge_points: ev.knowledge_points || [],
                related_topics: ev.related_topics || [],
                common_mistakes: ev.common_mistakes || [],
              },
              isSolving: false,
              isStreaming: false,
              expandedLayer: 1,
            });
            try { task.close(); } catch { /* already closed */ }
            resolve();
          } else if (ev.type === 'error') {
            settled = true;
            set({ isSolving: false, isStreaming: false });
            try { task.close(); } catch { /* already closed */ }
            reject(new Error(ev.message || '解题失败'));
          }
        });

        task.onError(() => fallback());
        task.onClose(() => { if (!settled) fallback(); });
      })();
    });
  },

  solve: async (stage) => {
    const { question } = get();
    if (!question.trim()) return;
    set({ isSolving: true, result: null, addedToMistakes: false });
    try {
      const result = await request<SolveResult>('/api/solve/deep', {
        method: 'POST',
        data: { question, stage, solve_type: 'deep' },
      });
      set({ result, isSolving: false, expandedLayer: 1 });
    } catch (err: any) {
      set({ isSolving: false });
      throw err;
    }
  },

  solveByPhoto: async (stage) => {
    let filePath: string;
    try {
      const res = await Taro.chooseImage({
        count: 1,
        sizeType: ['compressed'],
        sourceType: ['camera', 'album'],
      });
      filePath = res.tempFilePaths[0];
    } catch {
      return; // user cancelled the picker
    }
    if (!filePath) return;
    set({ isSolving: true, result: null, addedToMistakes: false });
    try {
      const base64 = Taro.getFileSystemManager().readFileSync(filePath, 'base64') as string;
      const data = await request<{ answer: string }>('/api/solve/vision', {
        method: 'POST',
        data: { image_base64: base64, stage },
      });
      set({
        result: {
          answer: data.answer,
          steps: [],
          knowledge_points: [],
          related_topics: [],
          common_mistakes: [],
        },
        isSolving: false,
        expandedLayer: 1,
      });
    } catch (err: any) {
      set({ isSolving: false });
      throw err;
    }
  },

  expandLayer: (layer) => set({ expandedLayer: layer }),

  askWhy: async (stepIndex, stepContent) => {
    const { result } = get();
    set({ isWhyLoading: true, expandedStepIndex: stepIndex });
    try {
      const data = await request<{ explanation: string }>('/api/solve/step-explain', {
        method: 'POST',
        data: {
          step_index: stepIndex,
          step_content: stepContent,
          question_context: result?.steps.map(s => s.content).join('\n') || '',
        },
      });
      set({ whyExplanation: data.explanation, isWhyLoading: false });
    } catch {
      set({ isWhyLoading: false });
    }
  },

  addToMistakes: async () => {
    const { question, result, addedToMistakes } = get();
    if (!result || addedToMistakes) return;
    await request('/api/me/mistakes', {
      method: 'POST',
      data: {
        question_text: question,
        correct_answer: result.answer,
        solution_steps: result.steps,
      },
    });
    set({ addedToMistakes: true });
  },

  reset: () => set({
    question: '',
    isSolving: false,
    result: null,
    expandedLayer: 1,
    expandedStepIndex: null,
    whyExplanation: '',
    addedToMistakes: false,
    streamingText: '',
    isStreaming: false,
  }),
}));
