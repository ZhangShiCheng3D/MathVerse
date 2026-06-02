import { useEffect, useState } from 'react';
import { View, Text } from '@tarojs/components';
import { request } from '../../services/api';
import { useUserStore } from '../../stores/user';

const MODES = [
  { id: 'math-1', label: '数学一' },
  { id: 'math-2', label: '数学二' },
  { id: 'math-3', label: '数学三' },
];

interface Estimate {
  estimated_score: number;
  score_range?: string;
  pass_probability: number;
  weak_areas: string[];
}

interface KgTopic { id: string; name: string }

export default function ScorePage() {
  const user = useUserStore((s) => s.user);
  const [mode, setMode] = useState(user?.exam_mode || 'math-1');
  const [est, setEst] = useState<Estimate | null>(null);
  const [loading, setLoading] = useState(false);
  const [kpNames, setKpNames] = useState<Record<string, string>>({});

  // Load KG once to map weak_areas (kp_id) → Chinese names.
  useEffect(() => {
    request<{ subjects: any[] }>('/api/learn/kg/kaoyan').then((kg) => {
      const map: Record<string, string> = {};
      kg.subjects?.forEach((s: any) =>
        s.chapters?.forEach((c: any) =>
          c.topics?.forEach((t: KgTopic) => { map[t.id] = t.name; })));
      setKpNames(map);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    setLoading(true);
    request<Estimate>(`/api/me/score/estimate?exam_mode=${mode}`)
      .then(setEst)
      .catch(() => setEst(null))
      .finally(() => setLoading(false));
  }, [mode]);

  const hasData = est && est.estimated_score > 0;

  return (
    <View style={{ minHeight: '100vh', backgroundColor: '#fff', padding: '16px' }}>
      {/* exam_mode segmented control */}
      <View style={{ display: 'flex', border: '1px solid #4F46E5', borderRadius: '9px', overflow: 'hidden', marginBottom: '16px' }}>
        {MODES.map((m) => (
          <Text
            key={m.id}
            onClick={() => setMode(m.id)}
            style={{
              flex: 1, textAlign: 'center', fontSize: '13px', padding: '8px 0',
              backgroundColor: mode === m.id ? '#4F46E5' : '#fff',
              color: mode === m.id ? '#fff' : '#4F46E5',
            }}
          >
            {m.label}
          </Text>
        ))}
      </View>

      {loading && <Text style={{ display: 'block', textAlign: 'center', color: '#9ca3af', padding: '32px' }}>估算中...</Text>}

      {!loading && !hasData && (
        <View style={{ textAlign: 'center', padding: '48px 24px' }}>
          <Text style={{ display: 'block', fontSize: '32px' }}>📈</Text>
          <Text style={{ display: 'block', color: '#9ca3af', marginTop: '8px' }}>先去做几道题，攒点数据再估分</Text>
        </View>
      )}

      {!loading && hasData && est && (
        <View>
          {/* Score circle */}
          <View style={{
            width: '140px', height: '140px', borderRadius: '50%', margin: '8px auto',
            border: '8px solid #4F46E5', display: 'flex', alignItems: 'center',
            justifyContent: 'center', flexDirection: 'column',
          }}>
            <Text style={{ fontSize: '36px', fontWeight: 'bold', color: '#4F46E5' }}>{est.estimated_score}</Text>
            <Text style={{ fontSize: '12px', color: '#9ca3af' }}>预测得分</Text>
          </View>
          <Text style={{ display: 'block', textAlign: 'center', fontSize: '13px', color: '#6b7280' }}>
            {est.score_range ? `区间 ${est.score_range} 分 · ` : ''}满分 150
          </Text>

          {/* Pass probability */}
          <View style={{ backgroundColor: '#f0fdf4', borderRadius: '12px', padding: '14px', margin: '16px 0', textAlign: 'center' }}>
            <Text style={{ display: 'block', fontSize: '13px', color: '#166534' }}>及格概率</Text>
            <Text style={{ display: 'block', fontSize: '24px', fontWeight: 'bold', color: '#166534' }}>{est.pass_probability}%</Text>
          </View>

          {/* Weak areas */}
          {est.weak_areas.length > 0 && (
            <View>
              <Text style={{ display: 'block', fontWeight: 'bold', marginBottom: '8px' }}>薄弱环节（优先突破）</Text>
              {est.weak_areas.map((kp) => (
                <View key={kp} style={{ display: 'flex', alignItems: 'center', gap: '8px', border: '1px solid #e5e7eb', borderRadius: '12px', padding: '10px', marginBottom: '8px' }}>
                  <Text style={{ padding: '2px 8px', borderRadius: '5px', fontSize: '11px', backgroundColor: '#fef2f2', color: '#dc2626' }}>弱</Text>
                  <Text style={{ fontSize: '14px' }}>{kpNames[kp] || kp}</Text>
                </View>
              ))}
            </View>
          )}

          <Text style={{ display: 'block', fontSize: '11.5px', color: '#d1d5db', textAlign: 'center', marginTop: '16px' }}>
            估分为蒙特卡洛粗略代理，仅供趋势参考
          </Text>
        </View>
      )}
    </View>
  );
}
