import { View, Text, Button } from '@tarojs/components';
import Taro from '@tarojs/taro';
import { useUserStore } from '../../stores/user';

const IS_H5 = process.env.TARO_ENV === 'h5';

export default function HomePage() {
  const user = useUserStore((s) => s.user);
  const login = useUserStore((s) => s.login);

  const onLogin = () => {
    if (IS_H5) Taro.navigateTo({ url: '/pages/login/index' });
    else login();
  };

  return (
    <View style={{ minHeight: '100vh', backgroundColor: '#fff' }}>
      {/* Hero Section */}
      <View style={{
        textAlign: 'center',
        padding: '48px 16px',
        background: 'linear-gradient(180deg, #4F46E5 0%, #6366f1 100%)',
        color: '#fff',
      }}>
        <Text style={{ fontSize: '28px', fontWeight: '800' }}>数界 MathVerse</Text>
        <Text style={{ display: 'block', marginTop: '8px', color: '#c7d2fe' }}>
          能讲、能解、能伴你学数学的 AI
        </Text>
        {!user && (
          <Button
            style={{
              marginTop: '24px',
              backgroundColor: '#fff',
              color: '#4F46E5',
              borderRadius: '9999px',
              padding: '8px 32px',
              fontWeight: '600',
            }}
            onClick={onLogin}
          >
            {IS_H5 ? '手机号一键登录' : '微信一键登录'}
          </Button>
        )}
      </View>

      {/* Three Entry Cards */}
      <View style={{ display: 'flex', padding: '16px', gap: '12px', marginTop: '16px' }}>
        {[
          { icon: '🔍', label: '解题', desc: '即问即解', path: '/pages/solve/index' },
          { icon: '📚', label: '学习', desc: '知识地图', path: '/pages/learn/index' },
          { icon: '📊', label: '我的', desc: '进度+错题', path: '/pages/me/index' },
        ].map((item) => (
          <View
            key={item.label}
            style={{
              flex: 1,
              padding: '16px',
              border: '1px solid #e5e7eb',
              borderRadius: '12px',
              textAlign: 'center',
            }}
            onClick={() => Taro.switchTab({ url: item.path })}
          >
            <Text style={{ fontSize: '24px' }}>{item.icon}</Text>
            <Text style={{ display: 'block', fontWeight: 'bold', marginTop: '4px' }}>
              {item.label}
            </Text>
            <Text style={{ display: 'block', fontSize: '12px', color: '#9ca3af' }}>
              {item.desc}
            </Text>
          </View>
        ))}
      </View>

      {/* Slogan */}
      <View style={{ textAlign: 'center', padding: '32px 0' }}>
        <Text style={{ fontSize: '16px', color: '#6b7280' }}>
          从一加一到高数，每一步都算数
        </Text>
      </View>
    </View>
  );
}
