import { vi, describe, it, expect, beforeEach } from 'vitest';

const handlers: any = {};
const sent: any[] = [];
const fakeTask = {
  onOpen: (cb: any) => { handlers.open = cb; },
  onMessage: (cb: any) => { handlers.msg = cb; },
  onError: (cb: any) => { handlers.error = cb; },
  onClose: (cb: any) => { handlers.close = cb; },
  send: (x: any) => sent.push(x),
  close: () => {},
};

vi.mock('@tarojs/taro', () => ({
  default: {
    connectSocket: () => fakeTask,
    getStorageSync: () => '',
  },
}));

import { useTutorStore } from './tutor';

describe('tutor store', () => {
  beforeEach(() => {
    sent.length = 0;
    useTutorStore.getState().reset();
  });

  it('send opens the socket, streams, and finalizes on done', () => {
    useTutorStore.getState().send('讲讲导数', 'college');
    expect(useTutorStore.getState().messages[0]).toEqual({ role: 'user', content: '讲讲导数' });

    handlers.open();
    expect(JSON.parse(sent[0].data).message).toBe('讲讲导数');

    handlers.msg({ data: JSON.stringify({ type: 'stream', content: '导数是' }) });
    expect(useTutorStore.getState().streaming).toBe('导数是');

    handlers.msg({ data: JSON.stringify({ type: 'result', content: '导数是变化率' }) });
    expect(useTutorStore.getState().messages[1]).toEqual({ role: 'assistant', content: '导数是变化率' });

    handlers.msg({ data: JSON.stringify({ type: 'done', session_id: 'abc' }) });
    const s = useTutorStore.getState();
    expect(s.isRunning).toBe(false);
    expect(s.sessionId).toBe('abc');
  });

  it('ask_user sets pending and reply sends a reply frame', () => {
    useTutorStore.getState().send('出题', 'college');
    handlers.open();
    handlers.msg({ data: JSON.stringify({ type: 'ask_user', content: '几年级' }) });
    expect(useTutorStore.getState().ask.pending).toBe(true);

    useTutorStore.getState().reply('高三');
    expect(useTutorStore.getState().ask.pending).toBe(false);
    expect(JSON.parse(sent[sent.length - 1].data)).toEqual({ type: 'reply', text: '高三' });
  });
});
