import { useEffect, useState } from 'react';
import { View, Text, Button } from '@tarojs/components';
import Taro from '@tarojs/taro';
import { request } from '../../services/api';

interface Plan { id: string; name: string; amount: number; days: number }
interface Sub {
  tier: string;
  tier_expires_at: string | null;
  active_subscription: { plan: string; expires_at: string } | null;
}

const TIER_LABEL: Record<string, string> = {
  free: '免费版', monthly: '月卡会员', quarterly: '季卡会员', yearly: '年卡会员',
};

export default function MembershipPage() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [sub, setSub] = useState<Sub | null>(null);
  const [selected, setSelected] = useState('quarterly');
  const [paying, setPaying] = useState(false);

  const fetchSub = () => request<Sub>('/api/pay/subscription').then(setSub).catch(() => {});

  useEffect(() => {
    request<{ plans: Plan[] }>('/api/pay/plans').then((d) => setPlans(d.plans)).catch(() => {});
    fetchSub();
  }, []);

  const pay = async () => {
    setPaying(true);
    try {
      const res = await request<{ prepay_params: any }>('/api/pay/wechat/prepay', {
        method: 'POST',
        data: { plan: selected },
      });
      await Taro.requestPayment({ ...res.prepay_params });
      Taro.showToast({ title: '开通成功', icon: 'success' });
      fetchSub();
    } catch {
      // WeChat merchant keys not yet configured → MOCK_SIGN is rejected.
      Taro.showToast({ title: '支付功能即将开放', icon: 'none' });
    }
    setPaying(false);
  };

  const sel = plans.find((p) => p.id === selected);
  const isPaid = sub && sub.tier !== 'free';

  return (
    <View style={{ minHeight: '100vh', backgroundColor: '#f3f4f6', padding: '14px' }}>
      {/* Current identity */}
      <View style={{ background: 'linear-gradient(135deg,#4F46E5,#6366f1)', color: '#fff', borderRadius: '12px', padding: '16px', marginBottom: '14px' }}>
        <Text style={{ display: 'block', fontSize: '13px', color: '#c7d2fe' }}>当前身份</Text>
        <Text style={{ display: 'block', fontSize: '18px', fontWeight: 'bold' }}>
          {sub ? (TIER_LABEL[sub.tier] || sub.tier) : '—'}
        </Text>
        <Text style={{ display: 'block', fontSize: '12px', color: '#c7d2fe' }}>
          {isPaid && sub?.tier_expires_at
            ? `有效期至 ${sub.tier_expires_at.slice(0, 10)}`
            : '每日 10 次解题额度'}
        </Text>
      </View>

      {/* Plan cards */}
      {plans.map((p) => {
        const hot = p.id === 'quarterly';
        const on = selected === p.id;
        return (
          <View
            key={p.id}
            onClick={() => setSelected(p.id)}
            style={{
              position: 'relative', textAlign: 'center', borderRadius: '14px', padding: '14px', marginBottom: '11px',
              border: on ? '2px solid #4F46E5' : '2px solid #e5e7eb',
              backgroundColor: on ? '#eef2ff' : '#fff',
            }}
          >
            {hot && (
              <Text style={{ position: 'absolute', top: '-10px', right: '14px', backgroundColor: '#f59e0b', color: '#fff', fontSize: '11px', padding: '2px 9px', borderRadius: '9999px' }}>超值</Text>
            )}
            <Text style={{ display: 'block', fontWeight: '600' }}>{p.name}</Text>
            <Text style={{ display: 'block' }}>
              <Text style={{ fontSize: '26px', fontWeight: 'bold', color: '#4F46E5' }}>¥{Math.round(p.amount / 100)}</Text>
              <Text style={{ fontSize: '12px', color: '#6b7280' }}> / {p.days}天</Text>
            </Text>
            {hot && <Text style={{ display: 'block', fontSize: '11.5px', color: '#9ca3af' }}>日均仅 {(p.amount / 100 / p.days).toFixed(2)} 元</Text>}
          </View>
        );
      })}

      <Button
        style={{ backgroundColor: '#4F46E5', color: '#fff', borderRadius: '9999px', fontSize: '15px', marginTop: '6px' }}
        loading={paying}
        disabled={paying || !sel}
        onClick={pay}
      >
        {sel ? `微信支付 ¥${Math.round(sel.amount / 100)} 开通${sel.name}` : '加载中...'}
      </Button>
    </View>
  );
}
