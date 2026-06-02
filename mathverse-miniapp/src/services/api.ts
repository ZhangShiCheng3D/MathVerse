import Taro from '@tarojs/taro';

// Override per-environment via TARO_APP_API_URL (Taro injects TARO_APP_* at build).
const BASE_URL = process.env.TARO_APP_API_URL || 'https://kuangyebar.cn';

let accessToken: string | null = null;
let refreshToken: string | null = null;

export function setTokens(access: string, refresh: string) {
  accessToken = access;
  refreshToken = refresh;
  Taro.setStorageSync('access_token', access);
  Taro.setStorageSync('refresh_token', refresh);
}

export function loadTokens() {
  try {
    accessToken = Taro.getStorageSync('access_token') || null;
    refreshToken = Taro.getStorageSync('refresh_token') || null;
  } catch {
    accessToken = null;
    refreshToken = null;
  }
}

async function refreshAccessToken(): Promise<boolean> {
  if (!refreshToken) return false;
  try {
    const res = await Taro.request({
      url: `${BASE_URL}/api/auth/refresh`,
      method: 'POST',
      data: { refresh_token: refreshToken },
    });
    if (res.statusCode === 200) {
      accessToken = (res.data as any).access_token;
      if (accessToken) {
        Taro.setStorageSync('access_token', accessToken);
      }
      return true;
    }
  } catch {
    // Refresh failed
  }
  return false;
}

export async function request<T = any>(
  path: string,
  options: {
    method?: 'GET' | 'POST' | 'PATCH' | 'DELETE';
    data?: any;
    requireAuth?: boolean;
  } = {}
): Promise<T> {
  const { method = 'GET', data, requireAuth = true } = options;

  if (!accessToken) loadTokens();

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (requireAuth && accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`;
  }

  try {
    const res = await Taro.request({
      url: `${BASE_URL}${path}`,
      method,
      data,
      header: headers,
    });

    if (res.statusCode === 401 && requireAuth && refreshToken) {
      const refreshed = await refreshAccessToken();
      if (refreshed) {
        return request<T>(path, options);
      }
      throw new Error('Authentication required');
    }

    if (res.statusCode === 429) {
      // Could be the solve quota OR the SMS resend rate-limit — use the
      // server's own message instead of assuming it's a quota error.
      throw new Error((res.data as any)?.detail || '操作过于频繁，请稍后再试');
    }

    if (res.statusCode >= 400) {
      throw new Error((res.data as any)?.detail || 'Request failed');
    }

    return res.data as T;
  } catch (err: any) {
    if (err.message && !err.message.includes('Request failed')) throw err;
    throw new Error('Network error');
  }
}
