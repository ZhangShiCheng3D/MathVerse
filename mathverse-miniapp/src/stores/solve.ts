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
  setQuestion: (q: string) => void;
  solve: (stage: string) => Promise<void>;
  expandLayer: (layer: 1 | 2 | 3) => void;
  askWhy: (stepIndex: number, stepContent: string) => Promise<void>;
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

  setQuestion: (q) => set({ question: q }),

  solve: async (stage) => {
    const { question } = get();
    if (!question.trim()) return;
    set({ isSolving: true, result: null });
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

  reset: () => set({
    question: '',
    isSolving: false,
    result: null,
    expandedLayer: 1,
    expandedStepIndex: null,
    whyExplanation: '',
  }),
}));
