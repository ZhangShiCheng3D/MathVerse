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
  grades: Record<number, { correct: boolean; feedback: string }>;
  addedMistakes: Record<number, boolean>;
  gradingIndex: number | null;
  activeTab: 'lecture' | 'exercise';
  isLoading: boolean;
  setStage: (stage: string) => void;
  fetchKg: () => Promise<void>;
  selectKp: (kp: KgNode) => void;
  fetchLecture: (kpName: string, kpId: string) => Promise<void>;
  fetchExercise: (kpName: string, kpId: string) => Promise<void>;
  gradeAnswer: (index: number, userAnswer: string) => Promise<void>;
  addExerciseMistake: (index: number, userAnswer: string) => Promise<void>;
}

const _subjectOf = (kpId: string): string => {
  if (kpId.startsWith('xd')) return '线性代数';
  if (kpId.startsWith('gl')) return '概率论与数理统计';
  if (kpId.startsWith('gs')) return '高等数学';
  return '';
};

export const useLearnStore = create<LearnStore>((set, get) => ({
  stage: 'college',
  kgData: null,
  selectedKp: null,
  lecture: '',
  exercises: [],
  grades: {},
  addedMistakes: {},
  gradingIndex: null,
  activeTab: 'lecture',
  isLoading: false,

  setStage: (stage) => set({ stage, selectedKp: null, lecture: '', exercises: [], grades: {}, addedMistakes: {} }),

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

  selectKp: (kp) => set({ selectedKp: kp, lecture: '', exercises: [], grades: {}, addedMistakes: {}, activeTab: 'lecture' }),

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
    set({ isLoading: true, activeTab: 'exercise', exercises: [], grades: {}, addedMistakes: {}, gradingIndex: null });
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

  gradeAnswer: async (index, userAnswer) => {
    const q = get().exercises[index];
    const kp = get().selectedKp;
    if (!q || !kp) return;
    set({ gradingIndex: index });
    try {
      const data = await request<{ correct: boolean; feedback: string }>('/api/learn/exercise/grade', {
        method: 'POST',
        data: {
          kp_id: kp.id,
          question: q.question,
          user_answer: userAnswer,
          reference_answer: q.answer,
        },
      });
      set((s) => ({
        grades: { ...s.grades, [index]: { correct: data.correct, feedback: data.feedback } },
        gradingIndex: null,
      }));
    } catch (e: any) {
      const feedback = e?.message === 'Authentication required' ? '请先登录后再判分' : '判分失败，请重试';
      set((s) => ({
        grades: { ...s.grades, [index]: { correct: false, feedback } },
        gradingIndex: null,
      }));
    }
  },

  addExerciseMistake: async (index, userAnswer) => {
    const q = get().exercises[index];
    const kp = get().selectedKp;
    if (!q || !kp || get().addedMistakes[index]) return;
    await request('/api/me/mistakes', {
      method: 'POST',
      data: {
        question_text: q.question,
        user_answer: userAnswer,
        correct_answer: q.answer,
        solution_steps: q.analysis ? [{ title: '解析', content: q.analysis }] : undefined,
        knowledge_point_id: kp.id,
        subject: _subjectOf(kp.id),
        difficulty: kp.difficulty,
      },
    });
    set((s) => ({ addedMistakes: { ...s.addedMistakes, [index]: true } }));
  },
}));
