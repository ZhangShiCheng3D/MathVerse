import { useState, useRef, useEffect } from 'react';
import { View, Text, Input, Button } from '@tarojs/components';
import Taro from '@tarojs/taro';
import { useUserStore } from '../../stores/user';

const PHONE_RE = /^1[3-9]\d{9}$/;

export default function LoginPage() {
  const sendSmsCode = useUserStore((s) => s.sendSmsCode);
  const loginByPhone = useUserStore((s) => s.loginByPhone);
  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [countdown, setCountdown] = useState(0);
  const [loggingIn, setLoggingIn] = useState(false);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => () => { if (timer.current) clearInterval(timer.current); }, []);

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
    if (!PHONE_RE.test(phone)) {
      Taro.showToast({ title: '请输入正确的手机号', icon: 'none' });
      return;
    }
    try {
      const { debugCode } = await sendSmsCode(phone);
      startCountdown();
      if (debugCode) {
        Taro.showToast({ title: `测试验证码：${debugCode}`, icon: 'none', duration: 4000 });
      } else {
        Taro.showToast({ title: '验证码已发送', icon: 'success' });
      }
    } catch (e: any) {
      Taro.showToast({ title: e?.message || '发送失败', icon: 'none' });
    }
  };

  const handleLogin = async () => {
    if (!PHONE_RE.test(phone) || code.length < 4) {
      Taro.showToast({ title: '请输入手机号和验证码', icon: 'none' });
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
    <View style={{ minHeight: '100vh', backgroundColor: '#fff', padding: '32px 24px' }}>
      <View style={{ textAlign: 'center', marginBottom: '32px' }}>
        <Text style={{ display: 'block', fontSize: '26px', fontWeight: '800', color: '#4F46E5' }}>数界 MathVerse</Text>
        <Text style={{ display: 'block', fontSize: '13px', color: '#9ca3af', marginTop: '4px' }}>手机号登录 / 注册</Text>
      </View>

      <Input
        type='number'
        maxlength={11}
        value={phone}
        placeholder='请输入手机号'
        onInput={(e) => setPhone(e.detail.value)}
        style={{ border: '1px solid #e5e7eb', borderRadius: '10px', padding: '12px', fontSize: '15px', marginBottom: '12px' }}
      />

      <View style={{ display: 'flex', gap: '8px', marginBottom: '20px' }}>
        <Input
          type='number'
          maxlength={6}
          value={code}
          placeholder='6 位验证码'
          onInput={(e) => setCode(e.detail.value)}
          style={{ flex: 1, border: '1px solid #e5e7eb', borderRadius: '10px', padding: '12px', fontSize: '15px' }}
        />
        <Button
          style={{
            whiteSpace: 'nowrap',
            padding: '0 14px',
            fontSize: '14px',
            borderRadius: '10px',
            border: '1px solid #4F46E5',
            backgroundColor: countdown > 0 ? '#f3f4f6' : '#fff',
            color: countdown > 0 ? '#9ca3af' : '#4F46E5',
            display: 'flex',
            alignItems: 'center',
          }}
          disabled={countdown > 0}
          onClick={handleSend}
        >
          {countdown > 0 ? `${countdown}s` : '获取验证码'}
        </Button>
      </View>

      <Button
        style={{ backgroundColor: '#4F46E5', color: '#fff', borderRadius: '9999px', fontSize: '16px', fontWeight: '600' }}
        loading={loggingIn}
        disabled={loggingIn}
        onClick={handleLogin}
      >
        登录
      </Button>

      <Text style={{ display: 'block', textAlign: 'center', fontSize: '12px', color: '#9ca3af', marginTop: '16px' }}>
        未注册手机号将自动创建账号
      </Text>
    </View>
  );
}
