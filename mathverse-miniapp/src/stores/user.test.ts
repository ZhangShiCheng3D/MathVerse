import { vi, describe, it, expect, beforeEach } from 'vitest';

const requestMock = vi.fn();
vi.mock('@tarojs/taro', () => ({ default: {} }));
vi.mock('../services/api', () => ({
  request: (...a: any[]) => requestMock(...a),
  setTokens: vi.fn(),
  loadTokens: vi.fn(),
}));

import { useUserStore } from './user';

describe('user store', () => {
  beforeEach(() => {
    requestMock.mockReset();
    useUserStore.setState({ user: null, isLogin: false, isLoading: false });
  });

  it('loginByPhone sets the user + login flag and hits the verify endpoint', async () => {
    requestMock.mockResolvedValue({
      access_token: 'a', refresh_token: 'r',
      user: { id: '1', nickname: '小明', avatar_url: null, current_stage: 'senior', exam_mode: null, tier: 'free', streak_days: 0 },
    });
    await useUserStore.getState().loginByPhone('13900000000', '314159');
    const s = useUserStore.getState();
    expect(s.isLogin).toBe(true);
    expect(s.user?.nickname).toBe('小明');
    expect(requestMock).toHaveBeenCalledWith('/api/auth/sms/verify', expect.objectContaining({ method: 'POST' }));
  });

  it('updateProfile updates the local user from the response', async () => {
    requestMock.mockResolvedValue({
      id: '1', nickname: '小红', avatar_url: null, current_stage: 'junior', exam_mode: null, tier: 'free', streak_days: 0,
    });
    await useUserStore.getState().updateProfile({ current_stage: 'junior' });
    expect(useUserStore.getState().user?.current_stage).toBe('junior');
  });
});
