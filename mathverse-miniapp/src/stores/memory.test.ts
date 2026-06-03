import { vi, describe, it, expect, beforeEach } from 'vitest';

const requestMock = vi.fn();
vi.mock('@tarojs/taro', () => ({ default: {} }));
vi.mock('../services/api', () => ({ request: (...a: any[]) => requestMock(...a) }));

import { useMemoryStore } from './memory';

describe('memory store', () => {
  beforeEach(() => {
    requestMock.mockReset();
    useMemoryStore.setState({ docs: [], loading: false, disabled: false, error: '', content: null, contentTitle: '' });
  });

  it('fetchOverview loads docs', async () => {
    requestMock.mockResolvedValue({ docs: [{ layer: 'L2', key: 'chat' }] });
    await useMemoryStore.getState().fetchOverview();
    expect(useMemoryStore.getState().docs[0].key).toBe('chat');
    expect(useMemoryStore.getState().disabled).toBe(false);
  });

  it('marks disabled on a 未启用 (403) error', async () => {
    requestMock.mockRejectedValue(new Error('引擎记忆查看未启用'));
    await useMemoryStore.getState().fetchOverview();
    expect(useMemoryStore.getState().disabled).toBe(true);
    expect(useMemoryStore.getState().error).toBe('');
  });

  it('openDoc loads raw content', async () => {
    requestMock.mockResolvedValue({ content: '# 记忆' });
    await useMemoryStore.getState().openDoc('L2', 'chat');
    expect(requestMock).toHaveBeenCalledWith('/api/memory/doc/L2/chat');
    expect(useMemoryStore.getState().content).toBe('# 记忆');
  });
});
