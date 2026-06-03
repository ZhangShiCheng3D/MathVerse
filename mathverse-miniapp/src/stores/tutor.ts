import Taro from '@tarojs/taro';
import { create } from 'zustand';

export type Capability = 'chat' | 'solve' | 'research' | 'visualize';

export interface TutorMessage {
  role: 'user' | 'assistant';
  content: string;
}

interface TutorStore {
  capability: Capability;
  messages: TutorMessage[];
  streaming: string;
  isRunning: boolean;
  ask: { pending: boolean; question: string };
  sessionId: string | null;
  error: string;
  setCapability: (c: Capability) => void;
  send: (text: string, stage: string, useRag?: boolean) => void;
  regenerate: (stage: string) => void;
  reply: (text: string) => void;
  reset: () => void;
}

// The live SocketTask is kept module-level (not in store state) so reply()/close()
// can reach it without it leaking into render or serialization.
let activeTask: any = null;

// Open a /ws/tutor socket and run one turn from `initPayload` (a normal start
// or a {type:'regenerate'} re-run). Shared by send() and regenerate().
const openTurnSocket = (set: any, get: any, initPayload: Record<string, any>) => {
  const startSid: string | null = get().sessionId;
  const base = process.env.TARO_APP_API_URL || 'https://kuangyebar.cn';
  const wsUrl = base.replace(/^http/, 'ws') + '/ws/tutor';
  let token = '';
  try { token = Taro.getStorageSync('access_token') || ''; } catch { /* no token */ }

  (async () => {
    let task: any;
    try {
      // h5 returns a Promise<SocketTask>; weapp returns it synchronously.
      task = Taro.connectSocket({ url: wsUrl });
      if (task && typeof task.then === 'function') task = await task;
    } catch {
      set({ isRunning: false, error: '连接失败' });
      return;
    }
    if (!task || typeof task.onMessage !== 'function') {
      set({ isRunning: false, error: '连接失败' });
      return;
    }
    activeTask = task;

    task.onOpen(() => task.send({ data: JSON.stringify({ token, ...initPayload }) }));

    task.onMessage((res: any) => {
      let ev: any;
      try { ev = JSON.parse(res.data); } catch { return; }
      switch (ev.type) {
        case 'stream':
          set((s: any) => ({ streaming: s.streaming + (ev.content || '') }));
          break;
        case 'ask_user':
          set({ ask: { pending: true, question: ev.content || '请补充信息' } });
          break;
        case 'result':
          set((s: any) => ({
            messages: [...s.messages, { role: 'assistant', content: ev.content || s.streaming }],
            streaming: '',
            ask: { pending: false, question: '' },
          }));
          break;
        case 'done':
          set((s: any) => ({
            isRunning: false,
            sessionId: ev.session_id || startSid,
            messages: s.streaming ? [...s.messages, { role: 'assistant', content: s.streaming }] : s.messages,
            streaming: '',
          }));
          try { task.close(); } catch { /* already closed */ }
          activeTask = null;
          break;
        case 'error':
          set({ isRunning: false, error: ev.content || '出错了', ask: { pending: false, question: '' } });
          try { task.close(); } catch { /* already closed */ }
          activeTask = null;
          break;
        default:
          break; // status / tool-trace events ignored for now
      }
    });

    task.onError(() => { set({ isRunning: false, error: '连接错误' }); activeTask = null; });
    task.onClose(() => { if (get().isRunning) set({ isRunning: false }); });
  })();
};

export const useTutorStore = create<TutorStore>((set, get) => ({
  capability: 'chat',
  messages: [],
  streaming: '',
  isRunning: false,
  ask: { pending: false, question: '' },
  sessionId: null,
  error: '',

  setCapability: (c) => set({ capability: c }),

  send: (text, stage, useRag = false) => {
    if (!text.trim() || get().isRunning) return;
    const { capability, sessionId } = get();
    set((s) => ({
      messages: [...s.messages, { role: 'user', content: text }],
      streaming: '',
      isRunning: true,
      error: '',
    }));
    openTurnSocket(set, get, { capability, message: text, session_id: sessionId, stage, use_rag: useRag });
  },

  regenerate: (stage) => {
    const { sessionId, isRunning } = get();
    if (!sessionId || isRunning) return;
    // Drop the trailing assistant bubble — the engine replaces it with a fresh run.
    set((s) => {
      const m = [...s.messages];
      if (m.length && m[m.length - 1].role === 'assistant') m.pop();
      return { messages: m, streaming: '', isRunning: true, error: '' };
    });
    openTurnSocket(set, get, { type: 'regenerate', session_id: sessionId, stage });
  },

  reply: (text) => {
    if (!activeTask) return;
    set({ ask: { pending: false, question: '' } });
    try { activeTask.send({ data: JSON.stringify({ type: 'reply', text }) }); } catch { /* socket gone */ }
  },

  reset: () => {
    try { activeTask?.close(); } catch { /* already closed */ }
    activeTask = null;
    set({ messages: [], streaming: '', isRunning: false, ask: { pending: false, question: '' }, sessionId: null, error: '' });
  },
}));
