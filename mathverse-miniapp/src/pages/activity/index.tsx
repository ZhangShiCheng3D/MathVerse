import { useEffect } from 'react';
import { View, Text, ScrollView } from '@tarojs/components';
import { useActivityStore } from '../../stores/activity';

const CAP_LABEL: Record<string, string> = {
  chat: '对话', solve: '解题', research: '研究', visualize: '可视化',
};

export default function ActivityPage() {
  const { list, loading, error, detail, detailLoading, fetchRecent, openEntry, closeDetail } = useActivityStore();

  useEffect(() => {
    fetchRecent();
  }, []);

  if (detail) {
    return (
      <View style={{ minHeight: '100vh', backgroundColor: '#f3f4f6', padding: '14px' }}>
        <Text onClick={closeDetail} style={{ display: 'block', color: '#4F46E5', marginBottom: '12px' }}>‹ 返回列表</Text>
        <Text style={{ display: 'block', fontSize: '18px', fontWeight: 'bold', marginBottom: '12px' }}>{detail.title || '会话'}</Text>
        <ScrollView scrollY style={{ height: '80vh' }}>
          {detail.content.messages.map((m, i) => (
            <View
              key={i}
              style={{
                maxWidth: '85%', marginBottom: '10px', padding: '10px 12px', borderRadius: '12px',
                marginLeft: m.role === 'user' ? 'auto' : '0',
                backgroundColor: m.role === 'user' ? '#4F46E5' : '#fff',
                color: m.role === 'user' ? '#fff' : '#111827',
                border: m.role === 'user' ? 'none' : '1px solid #e5e7eb',
              }}
            >
              <Text style={{ fontSize: '14px', whiteSpace: 'pre-wrap' }}>{m.content}</Text>
            </View>
          ))}
        </ScrollView>
      </View>
    );
  }

  return (
    <View style={{ minHeight: '100vh', backgroundColor: '#f3f4f6', padding: '14px' }}>
      <View style={{ backgroundColor: '#4F46E5', color: '#fff', borderRadius: '12px', padding: '16px', marginBottom: '12px' }}>
        <Text style={{ display: 'block', fontSize: '20px', fontWeight: 'bold' }}>AI 导师历史</Text>
        <Text style={{ display: 'block', fontSize: '12px', color: '#c7d2fe', marginTop: '4px' }}>回顾你与 AI 导师的历史对话</Text>
      </View>

      {loading && <Text style={{ display: 'block', textAlign: 'center', color: '#9ca3af', padding: '24px' }}>加载中...</Text>}
      {error !== '' && <Text style={{ display: 'block', textAlign: 'center', color: '#ef4444', padding: '8px' }}>{error}</Text>}

      {!loading && list.length === 0 && (
        <View style={{ textAlign: 'center', padding: '40px 24px' }}>
          <Text style={{ display: 'block', fontSize: '32px' }}>💬</Text>
          <Text style={{ display: 'block', color: '#9ca3af', marginTop: '8px' }}>还没有历史会话，去和 AI 导师聊聊吧</Text>
        </View>
      )}

      {list.map((a) => (
        <View
          key={a.id}
          style={{ backgroundColor: '#fff', border: '1px solid #e5e7eb', borderRadius: '12px', padding: '13px', marginBottom: '11px' }}
          onClick={() => openEntry(a.id)}
        >
          <View style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
            <Text style={{ padding: '2px 8px', borderRadius: '5px', fontSize: '11px', backgroundColor: '#dbeafe', color: '#1e40af' }}>
              {CAP_LABEL[a.capability || 'chat'] || a.capability}
            </Text>
            <Text style={{ fontSize: '15px', fontWeight: '600' }}>{a.title || '会话'}</Text>
          </View>
          {a.summary ? (
            <Text style={{ display: 'block', fontSize: '12px', color: '#9ca3af' }}>{a.summary}</Text>
          ) : null}
        </View>
      ))}

      {detailLoading && <Text style={{ display: 'block', textAlign: 'center', color: '#9ca3af', padding: '12px' }}>读取中...</Text>}
    </View>
  );
}
