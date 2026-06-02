import { useEffect, useState } from 'react';
import { View, Text, Button } from '@tarojs/components';
import { useReachBottom } from '@tarojs/taro';
import { request } from '../../services/api';

interface Step { title?: string; content?: string }
interface Mistake {
  id: string;
  question_text: string;
  subject: string;
  difficulty: number;
  knowledge_point_id: string | null;
  error_type: string | null;
  mastered: boolean;
  next_review_at: string | null;
  solution_steps: Step[];
  review_count: number;
}

const FILTERS: { label: string; val: boolean | undefined }[] = [
  { label: '全部', val: undefined },
  { label: '未掌握', val: false },
  { label: '已掌握', val: true },
];

const RATINGS = [
  { label: '没记住', rating: 1 },
  { label: '有点难', rating: 2 },
  { label: '记得', rating: 3 },
  { label: '很简单', rating: 4 },
];

const reviewLabel = (iso: string | null) => {
  if (!iso) return '未复习';
  const days = Math.ceil((new Date(iso).getTime() - Date.now()) / 86400000);
  if (days <= 0) return '今天复习';
  if (days === 1) return '明天复习';
  return `${days}天后复习`;
};

const stars = (n: number) => '★'.repeat(n) + '☆'.repeat(Math.max(0, 5 - n));

export default function MistakesPage() {
  const [filter, setFilter] = useState(0);
  const [items, setItems] = useState<Mistake[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [reviewingId, setReviewingId] = useState<string | null>(null);

  const load = async (p: number, replace: boolean) => {
    setLoading(true);
    const mastered = FILTERS[filter].val;
    const qs = `page=${p}&page_size=20` + (mastered === undefined ? '' : `&mastered=${mastered}`);
    try {
      const data = await request<{ items: Mistake[]; total: number }>(`/api/me/mistakes?${qs}`);
      setItems((prev) => (replace ? data.items : [...prev, ...data.items]));
      setTotal(data.total);
      setPage(p);
    } catch { /* falls through to empty state */ }
    setLoading(false);
    setLoaded(true);
  };

  useEffect(() => { setReviewingId(null); load(1, true); }, [filter]);
  useReachBottom(() => { if (items.length < total && !loading) load(page + 1, false); });

  const patch = async (id: string, body: { review_rating?: number; mastered?: boolean }) => {
    try {
      await request(`/api/me/mistakes/${id}`, { method: 'PATCH', data: body });
    } catch { /* keep UI; reload reflects server truth */ }
    setReviewingId(null);
    load(1, true);
  };

  return (
    <View style={{ minHeight: '100vh', backgroundColor: '#f3f4f6' }}>
      {/* Filter chips */}
      <View style={{ display: 'flex', gap: '8px', padding: '12px 16px', backgroundColor: '#fff' }}>
        {FILTERS.map((f, i) => (
          <Text
            key={f.label}
            onClick={() => setFilter(i)}
            style={{
              padding: '4px 14px',
              borderRadius: '9999px',
              fontSize: '13px',
              backgroundColor: filter === i ? '#4F46E5' : '#fff',
              color: filter === i ? '#fff' : '#6b7280',
              border: filter === i ? 'none' : '1px solid #e5e7eb',
            }}
          >
            {f.label}
          </Text>
        ))}
      </View>

      <View style={{ padding: '12px 16px' }}>
        {items.map((m) => (
          <View key={m.id} style={{ backgroundColor: '#fff', border: '1px solid #e5e7eb', borderRadius: '12px', padding: '13px', marginBottom: '11px' }}>
            <View style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '4px' }}>
              {!!m.subject && (
                <Text style={{ padding: '2px 8px', borderRadius: '5px', fontSize: '11px', backgroundColor: '#e0e7ff', color: '#4338ca' }}>{m.subject}</Text>
              )}
              {!!m.error_type && (
                <Text style={{ padding: '2px 8px', borderRadius: '5px', fontSize: '11px', backgroundColor: '#fef2f2', color: '#dc2626' }}>{m.error_type}</Text>
              )}
              {m.mastered && (
                <Text style={{ padding: '2px 8px', borderRadius: '5px', fontSize: '11px', backgroundColor: '#dcfce7', color: '#166534' }}>已掌握</Text>
              )}
              <Text style={{ fontSize: '11px', color: '#f59e0b' }}>{stars(m.difficulty)}</Text>
            </View>

            <Text style={{ display: 'block', fontSize: '13px', color: '#374151', margin: '7px 0', lineHeight: '1.5' }}>
              {m.question_text}
            </Text>
            <Text style={{ fontSize: '11.5px', color: '#9ca3af' }}>
              复习 {m.review_count} 次 · {m.mastered ? '已掌握' : reviewLabel(m.next_review_at)}
            </Text>

            {reviewingId === m.id ? (
              <View style={{ marginTop: '10px' }}>
                {m.solution_steps.length > 0 ? (
                  m.solution_steps.map((s, i) => (
                    <View key={i} style={{ padding: '10px', backgroundColor: '#f9fafb', borderRadius: '8px', marginBottom: '8px' }}>
                      {!!s.title && <Text style={{ display: 'block', fontWeight: 'bold', fontSize: '13px', color: '#4338ca' }}>{s.title}</Text>}
                      <Text style={{ display: 'block', fontSize: '13px', color: '#374151', marginTop: '2px' }}>{s.content}</Text>
                    </View>
                  ))
                ) : (
                  <Text style={{ display: 'block', fontSize: '13px', color: '#9ca3af', marginBottom: '8px' }}>这道题暂无解题步骤</Text>
                )}
                <Text style={{ display: 'block', fontSize: '12px', color: '#6b7280', marginBottom: '6px' }}>这次复习的掌握程度？</Text>
                <View style={{ display: 'flex', gap: '6px' }}>
                  {RATINGS.map((r) => (
                    <Text
                      key={r.rating}
                      onClick={() => patch(m.id, { review_rating: r.rating })}
                      style={{ flex: 1, textAlign: 'center', fontSize: '12px', padding: '8px 0', borderRadius: '8px', border: '1px solid #e5e7eb', color: '#374151' }}
                    >
                      {r.label}
                    </Text>
                  ))}
                </View>
                <Button
                  style={{ marginTop: '8px', backgroundColor: '#4F46E5', color: '#fff', borderRadius: '9999px', fontSize: '14px' }}
                  onClick={() => patch(m.id, { mastered: true })}
                >
                  ✓ 标记已掌握
                </Button>
                <Button
                  style={{ marginTop: '6px', backgroundColor: 'transparent', color: '#9ca3af', fontSize: '13px', padding: 0 }}
                  onClick={() => setReviewingId(null)}
                >
                  收起
                </Button>
              </View>
            ) : (
              !m.mastered && (
                <Button
                  style={{ marginTop: '8px', backgroundColor: '#fff', color: '#4F46E5', border: '1px solid #4F46E5', borderRadius: '9999px', fontSize: '14px' }}
                  onClick={() => setReviewingId(m.id)}
                >
                  复习这道题 →
                </Button>
              )
            )}
          </View>
        ))}

        {loading && <Text style={{ display: 'block', textAlign: 'center', color: '#9ca3af', padding: '16px' }}>加载中...</Text>}
        {loaded && !loading && items.length === 0 && (
          <View style={{ textAlign: 'center', padding: '48px 24px' }}>
            <Text style={{ display: 'block', fontSize: '32px' }}>📕</Text>
            <Text style={{ display: 'block', color: '#9ca3af', marginTop: '8px' }}>
              {FILTERS[filter].val === true ? '还没有已掌握的错题' : '还没有错题，去解题页把不会的加进来'}
            </Text>
          </View>
        )}
        {!loading && items.length > 0 && items.length >= total && (
          <Text style={{ display: 'block', textAlign: 'center', color: '#d1d5db', fontSize: '12px', padding: '12px' }}>没有更多了</Text>
        )}
      </View>
    </View>
  );
}
