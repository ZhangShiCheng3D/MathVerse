import { vi, describe, it, expect, beforeEach } from 'vitest';

const requestMock = vi.fn();
vi.mock('@tarojs/taro', () => ({ default: {} }));
vi.mock('../services/api', () => ({ request: (...a: any[]) => requestMock(...a) }));

import { useNotebookStore } from './notebook';

describe('notebook store', () => {
  beforeEach(() => {
    requestMock.mockReset();
    useNotebookStore.setState({ list: [], loading: false, busy: false, error: '' });
  });

  it('fetchList loads notebooks', async () => {
    requestMock.mockResolvedValue({ notebooks: [{ id: 'nb1', name: '线代' }] });
    await useNotebookStore.getState().fetchList();
    expect(useNotebookStore.getState().list[0].id).toBe('nb1');
    expect(requestMock).toHaveBeenCalledWith('/api/notebook/list');
  });

  it('create posts then refreshes', async () => {
    requestMock.mockResolvedValue({ notebooks: [] });
    await useNotebookStore.getState().create('新本子');
    expect(requestMock).toHaveBeenCalledWith('/api/notebook/create', { method: 'POST', data: { name: '新本子' } });
  });

  it('addNote posts a chat record', async () => {
    requestMock.mockResolvedValue({ ok: true });
    await useNotebookStore.getState().addNote('nb1', '极限', '= -1/6');
    expect(requestMock).toHaveBeenCalledWith('/api/notebook/nb1/record', {
      method: 'POST',
      data: { title: '极限', user_query: '极限', output: '= -1/6', record_type: 'chat' },
    });
  });
});
