import { vi, describe, it, expect, beforeEach } from 'vitest';

const requestMock = vi.fn();
vi.mock('@tarojs/taro', () => ({ default: {} }));
vi.mock('../services/api', () => ({ request: (...a: any[]) => requestMock(...a) }));

import { useBookStore } from './book';

describe('book store', () => {
  beforeEach(() => {
    requestMock.mockReset();
    useBookStore.setState({ list: [], loading: false, busy: false, error: '', detail: null, detailLoading: false, page: null });
  });

  it('create posts the intent and returns the book id', async () => {
    requestMock
      .mockResolvedValueOnce({ book_id: 'bk1' })  // create
      .mockResolvedValueOnce({ books: [{ id: 'bk1', title: 'x' }] });  // fetchList
    const id = await useBookStore.getState().create('讲讲线代');
    expect(id).toBe('bk1');
    expect(requestMock).toHaveBeenCalledWith('/api/book/create', { method: 'POST', data: { user_intent: '讲讲线代' } });
  });

  it('generate posts to the generate endpoint then refreshes', async () => {
    requestMock.mockResolvedValueOnce({}).mockResolvedValueOnce({ books: [] });
    await useBookStore.getState().generate('bk1');
    expect(requestMock).toHaveBeenCalledWith('/api/book/bk1/generate', { method: 'POST' });
  });

  it('open loads book detail with pages', async () => {
    requestMock.mockResolvedValue({ book: { id: 'bk1', title: 'x' }, pages: [{ id: 'p1', title: '第一章' }] });
    await useBookStore.getState().open('bk1');
    expect(useBookStore.getState().detail?.pages).toHaveLength(1);
    expect(requestMock).toHaveBeenCalledWith('/api/book/bk1');
  });
});
