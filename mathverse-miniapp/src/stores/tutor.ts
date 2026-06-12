import Taro from '@tarojs/taro';
import { create } from 'zustand';
import { request } from '../services/api';

export type Capability = 'chat' | 'solve' | 'research' | 'visualize';

export interface CapabilityMeta {
  id: Capability;
  label: string;
  description?: string;
}

// Bootstrap fallback only — the authoritative list comes from the server
// (GET /api/tutor/capabilities) via fetchCapabilities(), so front/back can't drift.
const DEFAULT_CAPABILITIES: CapabilityMeta[] = [
  { id: 'chat', label: '对话' },
  { id: 'solve', label: '解题' },
  { id: 'research', label: '深度研究' },
  { id: 'visualize', label: '可视化' },
];

export interface TutorMessage {
  role: 'user' | 'assistant';
  content: string;
}

interface TutorStore {
  capability: Capability;
  capabilities: CapabilityMeta[];
  messages: TutorMessage[];
  streaming: string;
  isRunning: boolean;
  ask: { pending: boolean; question: string };
  sessionId: string | null;
  error: string;
  setCapability: (c: Capability) => void;
  fetchCapabilities: () => Promise<void>;
  send: (text: string, stage: string, useRag?: boolean) => void;
  regenerate: (stage: string) => void;
  reply: (text: string) => void;
  reset: () => void;
}

// The live SocketTask is kept module-level (not in store state) so reply()/close()
// can reach it without it leaking into render or serialization.
let activeTask: any = null;

// Regenerate drops the trailing assistant bubble only once the fresh run actually
// produces output — so a failed connection doesn't lose the previous answer.
let pendingRegenPop = false;

const popStaleAssistant = (messages: TutorMessage[]): TutorMessage[] => {
  if (!pendingRegenPop) return messages;
  pendingRegenPop = false;
  if (messages.length && messages[messages.length - 1].role === 'assistant') {
    return messages.slice(0, -1);
  }
  return messages;
};

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
          set((s: any) => ({
            messages: popStaleAssistant(s.messages),
            streaming: s.streaming + (ev.content || ''),
          }));
          break;
        case 'ask_user':
          set({ ask: { pending: true, question: ev.content || '请补充信息' } });
          break;
        case 'result':
          set((s: any) => ({
            messages: [...popStaleAssistant(s.messages), { role: 'assistant', content: ev.content || s.streaming }],
            streaming: '',
            ask: { pending: false, question: '' },
          }));
          break;
        case 'done':
          // A regen that produced no output keeps the previous answer in place.
          pendingRegenPop = false;
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
          pendingRegenPop = false;
          set({ isRunning: false, error: ev.content || '出错了', ask: { pending: false, question: '' } });
          try { task.close(); } catch { /* already closed */ }
          activeTask = null;
          break;
        default:
          break; // status / tool-trace events ignored for now
      }
    });

    task.onError(() => { pendingRegenPop = false; set({ isRunning: false, error: '连接错误' }); activeTask = null; });
    task.onClose(() => { if (get().isRunning) set({ isRunning: false }); });
  })();
};

export const useTutorStore = create<TutorStore>((set, get) => ({
  capability: 'chat',
  capabilities: DEFAULT_CAPABILITIES,
  messages: [],
  streaming: '',
  isRunning: false,
  ask: { pending: false, question: '' },
  sessionId: null,
  error: '',

  setCapability: (c) => set({ capability: c }),

  fetchCapabilities: async () => {
    try {
      const res = await request<{ capabilities: CapabilityMeta[] }>(
        '/api/tutor/capabilities', { requireAuth: false }
      );
      if (res?.capabilities?.length) set({ capabilities: res.capabilities });
    } catch { /* keep the bootstrap defaults on failure */ }
  },

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
    // The trailing assistant bubble is dropped lazily (popStaleAssistant) when
    // the fresh run starts producing output.
    pendingRegenPop = true;
    set({ streaming: '', isRunning: true, error: '' });
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
    pendingRegenPop = false;
    set({ messages: [], streaming: '', isRunning: false, ask: { pending: false, question: '' }, sessionId: null, error: '' });
  },
}));
