import { vi, describe, it, expect, beforeEach } from 'vitest';

const requestMock = vi.fn();
const store: Record<string, string> = {};

vi.mock('@tarojs/taro', () => ({
  default: {
    request: (opts: any) => requestMock(opts),
    getStorageSync: (k: string) => store[k] || '',
    setStorageSync: (k: string, v: string) => { store[k] = v; },
  },
}));

import { request } from './api';

describe('api.request', () => {
  beforeEach(() => { requestMock.mockReset(); });

  it('returns the body on 200', async () => {
    requestMock.mockResolvedValue({ statusCode: 200, data: { ok: 1 } });
    await expect(request('/x', { requireAuth: false })).resolves.toEqual({ ok: 1 });
  });

  it('429 surfaces the server message, not a hardcoded quota string', async () => {
    // Regression: SMS resend rate-limit (429) must not show "今日免费额度已用完".
    requestMock.mockResolvedValue({
      statusCode: 429,
      data: { detail: '验证码发送过于频繁，请稍后再试' },
    });
    await expect(request('/auth/sms/send', { requireAuth: false }))
      .rejects.toThrow('验证码发送过于频繁，请稍后再试');
  });

  it('maps >=400 to the server detail', async () => {
    requestMock.mockResolvedValue({ statusCode: 400, data: { detail: '手机号格式不正确' } });
    await expect(request('/x', { requireAuth: false })).rejects.toThrow('手机号格式不正确');
  });

  it('wraps a thrown transport error as a network error', async () => {
    requestMock.mockRejectedValue(new Error('Request failed'));
    await expect(request('/x', { requireAuth: false })).rejects.toThrow('Network error');
  });
});
