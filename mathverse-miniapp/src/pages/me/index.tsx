import { useEffect, useState } from 'react';
import { View, Text, ScrollView, Button } from '@tarojs/components';
import Taro from '@tarojs/taro';
import { request } from '../../services/api';
import { useUserStore } from '../../stores/user';

interface ProgressData {
  total_questions: number;
  questions_attempted: number;
  questions_correct: number;
  accuracy: number;
  streak_days: number;
  knowledge_points_learned: number;
  total_knowledge_points: number;
}

export default function MePage() {
  const user = useUserStore((s) => s.user);
  const login = useUserStore((s) => s.login);
  const onLogin = () => {
    if (process.env.TARO_ENV === 'h5') Taro.navigateTo({ url: '/pages/login/index' });
    else login();
  };
  const [progress, setProgress] = useState<ProgressData | null>(null);
  const [reviewCount, setReviewCount] = useState(0);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!user) return;
    setLoading(true);
    Promise.all([
      request<ProgressData>('/api/me/progress').catch(() => null),
      request<{ count: number }>('/api/me/mistakes/review-today').catch(() => null),
    ]).then(([prog, review]) => {
      if (prog) setProgress(prog);
      if (review) setReviewCount(review.count);
      setLoading(false);
    });
  }, [user]);

  // Not logged in
  if (!user) {
    return (
      <View style={{ padding: '32px', textAlign: 'center' }}>
        <Text style={{ color: '#6b7280', display: 'block', marginBottom: '16px' }}>
          登录后查看学习数据
        </Text>
        <Button
          style={{
            backgroundColor: '#4F46E5',
            color: '#fff',
            borderRadius: '9999px',
          }}
          onClick={onLogin}
        >
          {process.env.TARO_ENV === 'h5' ? '手机号登录' : '微信登录'}
        </Button>
      </View>
    );
  }

  return (
    <ScrollView style={{ minHeight: '100vh', backgroundColor: '#f3f4f6' }}>
      {/* User Header */}
      <View style={{
        backgroundColor: '#4F46E5',
        color: '#fff',
        padding: '24px 16px',
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
      }}>
        <View style={{
          width: '64px',
          height: '64px',
          borderRadius: '50%',
          backgroundColor: 'rgba(255,255,255,0.2)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}>
          <Text style={{ fontSize: '24px', fontWeight: 'bold' }}>
            {user.nickname[0]}
          </Text>
        </View>
        <View>
          <Text style={{ fontSize: '18px', fontWeight: 'bold' }}>{user.nickname}</Text>
          <Text style={{ display: 'block', color: '#c7d2fe', fontSize: '14px' }}>
            {user.tier === 'free' ? '免费版' : user.tier} · 🔥 连续 {user.streak_days} 天
          </Text>
        </View>
      </View>

      {/* Stats */}
      {progress && (
        <View style={{ display: 'flex', padding: '16px', gap: '8px' }}>
          {[
            { val: progress.questions_attempted || 0, label: '累计做题' },
            { val: `${progress.accuracy || 0}%`, label: '正确率' },
            { val: progress.knowledge_points_learned || 0, label: '已掌握知识点' },
          ].map((s) => (
            <View
              key={s.label}
              style={{
                flex: 1,
                backgroundColor: '#fff',
                padding: '12px',
                borderRadius: '12px',
                textAlign: 'center',
              }}
            >
              <Text style={{ display: 'block', fontSize: '20px', fontWeight: 'bold', color: '#4F46E5' }}>
                {s.val}
              </Text>
              <Text style={{ display: 'block', fontSize: '12px', color: '#9ca3af' }}>
                {s.label}
              </Text>
            </View>
          ))}
        </View>
      )}

      {loading && (
        <View style={{ padding: '24px', textAlign: 'center' }}>
          <Text style={{ color: '#9ca3af' }}>加载中...</Text>
        </View>
      )}

      {/* Quick Actions */}
      <View style={{ padding: '16px' }}>
        <View style={{ backgroundColor: '#fff', borderRadius: '12px', overflow: 'hidden' }}>
          {[
            { icon: '📕', label: '错题本', badge: reviewCount > 0 ? `${reviewCount}题待复习` : null, path: '/pages/mistakes/index' },
            { icon: '📋', label: '今日计划', path: '/pages/plan/index' },
            { icon: '📈', label: '估分预测', path: '/pages/score/index' },
            { icon: '⭐', label: '升级会员', path: '/pages/membership/index' },
          ].map((item) => (
            <View
              key={item.label}
              onClick={() => Taro.navigateTo({ url: item.path })}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '16px',
                borderBottom: '1px solid #f3f4f6',
              }}
            >
              <View style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <Text style={{ fontSize: '20px' }}>{item.icon}</Text>
                <Text style={{ fontSize: '16px' }}>{item.label}</Text>
              </View>
              <View style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                {item.badge && (
                  <Text style={{
                    padding: '2px 8px',
                    backgroundColor: '#fef2f2',
                    color: '#dc2626',
                    fontSize: '12px',
                    borderRadius: '9999px',
                  }}>
                    {item.badge}
                  </Text>
                )}
                <Text style={{ color: '#d1d5db' }}>→</Text>
              </View>
            </View>
          ))}
        </View>
      </View>
    </ScrollView>
  );
}
