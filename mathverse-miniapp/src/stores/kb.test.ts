import { vi, describe, it, expect, beforeEach } from 'vitest';

const requestMock = vi.fn();
vi.mock('@tarojs/taro', () => ({ default: {} }));
vi.mock('../services/api', () => ({ request: (...a: any[]) => requestMock(...a) }));

import { useKbStore } from './kb';

describe('kb store', () => {
  beforeEach(() => {
    requestMock.mockReset();
    useKbStore.setState({ list: [], loading: false, busy: false, error: '' });
  });

  it('fetchList loads the knowledge bases', async () => {
    requestMock.mockResolvedValue({
      knowledge_bases: [{ name: 'mykb', read_only: false, shared: false, status: 'ready', statistics: {} }],
    });
    await useKbStore.getState().fetchList();
    const s = useKbStore.getState();
    expect(s.list).toHaveLength(1);
    expect(s.list[0].name).toBe('mykb');
    expect(requestMock).toHaveBeenCalledWith('/api/kb/list');
  });

  it('seedCurriculum posts to the stage seed endpoint then refreshes', async () => {
    requestMock.mockResolvedValue({ knowledge_bases: [] });
    await useKbStore.getState().seedCurriculum('senior');
    expect(requestMock).toHaveBeenCalledWith('/api/kb/curriculum/senior/seed', { method: 'POST' });
  });

  it('remove deletes then refreshes', async () => {
    requestMock.mockResolvedValue({ knowledge_bases: [] });
    await useKbStore.getState().remove('mykb');
    expect(requestMock).toHaveBeenCalledWith('/api/kb/mykb', { method: 'DELETE' });
  });
});
