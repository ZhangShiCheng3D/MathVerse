import { create } from 'zustand';
import { request } from '../services/api';

interface KgNode {
  id: string;
  name: string;
  difficulty: number;
  mastery?: number;
}

interface KgSubject {
  id: string;
  name: string;
  chapters: {
    id: string;
    name: string;
    frequency: string;
    topics: KgNode[];
  }[];
}

interface Question {
  type: string;
  question: string;
  options?: string[];
  answer: string;
  analysis?: string;
}

interface LearnStore {
  stage: string;
  kgData: KgSubject[] | null;
  selectedKp: KgNode | null;
  lecture: string;
  exercises: Question[];
  activeTab: 'lecture' | 'exercise';
  isLoading: boolean;
  setStage: (stage: string) => void;
  fetchKg: () => Promise<void>;
  selectKp: (kp: KgNode) => void;
  fetchLecture: (kpName: string, kpId: string) => Promise<void>;
  fetchExercise: (kpName: string, kpId: string) => Promise<void>;
}

export const useLearnStore = create<LearnStore>((set, get) => ({
  stage: 'college',
  kgData: null,
  selectedKp: null,
  lecture: '',
  exercises: [],
  activeTab: 'lecture',
  isLoading: false,

  setStage: (stage) => set({ stage, selectedKp: null, lecture: '', exercises: [] }),

  fetchKg: async () => {
    set({ isLoading: true });
    try {
      const data = await request<{ subjects: KgSubject[] }>(
        `/api/learn/kg/${get().stage}`
      );
      set({ kgData: data.subjects, isLoading: false });
    } catch {
      set({ isLoading: false });
    }
  },

  selectKp: (kp) => set({ selectedKp: kp, lecture: '', exercises: [], activeTab: 'lecture' }),

  fetchLecture: async (kpName, kpId) => {
    set({ isLoading: true });
    try {
      const data = await request<{ lecture: string }>('/api/learn/lecture', {
        method: 'POST',
        data: { kp_name: kpName, kp_id: kpId, stage: get().stage },
      });
      set({ lecture: data.lecture, isLoading: false, activeTab: 'lecture' });
    } catch {
      set({ isLoading: false });
    }
  },

  fetchExercise: async (kpName, kpId) => {
    set({ isLoading: true, activeTab: 'exercise', exercises: [] });
    try {
      const data = await request<{ questions: Question[] }>('/api/learn/exercise/generate', {
        method: 'POST',
        data: { kp_name: kpName, kp_id: kpId, stage: get().stage, count: 3 },
      });
      set({ exercises: data.questions, isLoading: false });
    } catch {
      set({ isLoading: false });
    }
  },
}));
