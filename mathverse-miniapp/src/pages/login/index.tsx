import { useState, useRef, useEffect } from 'react';
import { View, Text, Input } from '@tarojs/components';
import Taro from '@tarojs/taro';
import { useUserStore } from '../../stores/user';

const PHONE_RE = /^1[3-9]\d{9}$/;
// Interim master code while the Tencent SMS sign/template approval is pending.
const MASTER_CODE = '314159';

export default function LoginPage() {
  const sendSmsCode = useUserStore((s) => s.sendSmsCode);
  const loginByPhone = useUserStore((s) => s.loginByPhone);
  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [countdown, setCountdown] = useState(0);
  const [loggingIn, setLoggingIn] = useState(false);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => () => { if (timer.current) clearInterval(timer.current); }, []);

  const phoneOk = PHONE_RE.test(phone);
  const canLogin = phoneOk && code.length >= 4 && !loggingIn;

  const startCountdown = () => {
    setCountdown(60);
    timer.current = setInterval(() => {
      setCountdown((c) => {
        if (c <= 1) {
          if (timer.current) clearInterval(timer.current);
          return 0;
        }
        return c - 1;
      });
    }, 1000);
  };

  const handleSend = async () => {
    if (countdown > 0) return;
    if (!phoneOk) {
      Taro.showToast({ title: '请输入正确的手机号', icon: 'none' });
      return;
    }
    try {
      const { debugCode } = await sendSmsCode(phone);
      startCountdown();
      if (debugCode) {
        setCode(debugCode); // dev mode: prefill so testing is one tap
        Taro.showToast({ title: `测试验证码 ${debugCode} 已填入`, icon: 'none', duration: 3000 });
      } else {
        Taro.showToast({ title: '验证码已发送', icon: 'success' });
      }
    } catch (e: any) {
      Taro.showToast({ title: e?.message || '发送失败', icon: 'none' });
    }
  };

  const handleLogin = async () => {
    if (!canLogin) {
      Taro.showToast({ title: phoneOk ? '请输入验证码' : '请输入正确的手机号', icon: 'none' });
      return;
    }
    setLoggingIn(true);
    try {
      await loginByPhone(phone, code);
      Taro.showToast({ title: '登录成功', icon: 'success' });
      setTimeout(() => {
        Taro.navigateBack().catch(() => Taro.switchTab({ url: '/pages/index/index' }));
      }, 600);
    } catch (e: any) {
      Taro.showToast({ title: e?.message || '登录失败', icon: 'none' });
    }
    setLoggingIn(false);
  };

  return (
    <View style={{ minHeight: '100vh', backgroundColor: '#fff', padding: '48px 28px 0' }}>
      {/* Brand */}
      <View style={{ textAlign: 'center', marginBottom: '40px' }}>
        <Text style={{ display: 'block', fontSize: '30px', fontWeight: '800', color: '#4F46E5' }}>数界 MathVerse</Text>
        <Text style={{ display: 'block', fontSize: '14px', color: '#9ca3af', marginTop: '6px' }}>手机号登录 / 注册</Text>
      </View>

      {/* Phone */}
      <Text style={{ display: 'block', fontSize: '13px', color: '#6b7280', marginBottom: '6px' }}>手机号</Text>
      <Input
        type='number'
        maxlength={11}
        value={phone}
        placeholder='请输入手机号'
        placeholderStyle='color:#c0c4cc'
        onInput={(e) => setPhone(e.detail.value)}
        style={{
          width: '100%', height: '50px', lineHeight: '50px', boxSizing: 'border-box',
          border: '1px solid #e5e7eb', borderRadius: '12px', padding: '0 14px',
          fontSize: '16px', backgroundColor: '#fafafa', marginBottom: '18px',
        }}
      />

      {/* Code + send */}
      <Text style={{ display: 'block', fontSize: '13px', color: '#6b7280', marginBottom: '6px' }}>验证码</Text>
      <View style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '28px' }}>
        <Input
          type='number'
          maxlength={6}
          value={code}
          placeholder='6 位验证码'
          placeholderStyle='color:#c0c4cc'
          onInput={(e) => setCode(e.detail.value)}
          style={{
            flex: 1, height: '50px', lineHeight: '50px', boxSizing: 'border-box',
            border: '1px solid #e5e7eb', borderRadius: '12px', padding: '0 14px',
            fontSize: '16px', backgroundColor: '#fafafa',
          }}
        />
        <View
          onClick={handleSend}
          style={{
            width: '116px', height: '50px', lineHeight: '50px', textAlign: 'center',
            borderRadius: '12px', fontSize: '14px', boxSizing: 'border-box',
            border: `1px solid ${countdown > 0 ? '#e5e7eb' : '#4F46E5'}`,
            color: countdown > 0 ? '#9ca3af' : '#4F46E5',
            backgroundColor: countdown > 0 ? '#f9fafb' : '#fff',
          }}
        >
          {countdown > 0 ? `${countdown}s` : '获取验证码'}
        </View>
      </View>

      {/* Login */}
      <View
        onClick={handleLogin}
        style={{
          height: '50px', lineHeight: '50px', textAlign: 'center', borderRadius: '9999px',
          fontSize: '17px', fontWeight: '600', color: '#fff',
          backgroundColor: canLogin ? '#4F46E5' : '#c7d2fe',
        }}
      >
        {loggingIn ? '登录中…' : '登录'}
      </View>

      {/* Interim master-code hint (remove once real SMS is live) */}
      <View style={{ marginTop: '18px', padding: '10px 14px', backgroundColor: '#eef2ff', borderRadius: '10px' }}>
        <Text style={{ fontSize: '13px', color: '#4338ca' }}>
          短信审批中：测试期间验证码请填 <Text style={{ fontWeight: '700' }}>{MASTER_CODE}</Text> 直接登录
        </Text>
      </View>

      <Text style={{ display: 'block', textAlign: 'center', fontSize: '12px', color: '#9ca3af', marginTop: '16px' }}>
        未注册手机号将自动创建账号
      </Text>
    </View>
  );
}
