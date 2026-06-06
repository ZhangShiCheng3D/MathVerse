import { vi, describe, it, expect, beforeEach } from 'vitest';

const requestMock = vi.fn();
vi.mock('@tarojs/taro', () => ({ default: {} }));
vi.mock('../services/api', () => ({ request: (...a: any[]) => requestMock(...a) }));

import { useActivityStore } from './activity';

describe('activity store', () => {
  beforeEach(() => {
    requestMock.mockReset();
    useActivityStore.setState({ list: [], loading: false, error: '', detail: null, detailLoading: false });
  });

  it('fetchRecent loads the activity list', async () => {
    requestMock.mockResolvedValue({ activities: [{ id: 'mv_u_s1', title: '会话', capability: 'solve' }] });
    await useActivityStore.getState().fetchRecent();
    expect(useActivityStore.getState().list[0].id).toBe('mv_u_s1');
    expect(requestMock).toHaveBeenCalledWith('/api/activity/recent');
  });

  it('openEntry loads a session detail', async () => {
    requestMock.mockResolvedValue({ id: 'mv_u_s1', title: '会话', content: { messages: [{ role: 'user', content: 'hi' }] } });
    await useActivityStore.getState().openEntry('mv_u_s1');
    expect(requestMock).toHaveBeenCalledWith('/api/activity/mv_u_s1');
    expect(useActivityStore.getState().detail?.content.messages).toHaveLength(1);
  });
});
