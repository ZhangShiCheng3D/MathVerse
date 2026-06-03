import { useEffect } from 'react';
import { View, Text, ScrollView } from '@tarojs/components';
import { useMemoryStore } from '../../stores/memory';

export default function MemoryPage() {
  const { docs, loading, disabled, error, content, contentTitle, fetchOverview, openDoc, closeDoc } = useMemoryStore();

  useEffect(() => {
    fetchOverview();
  }, []);

  if (content !== null) {
    return (
      <View style={{ minHeight: '100vh', backgroundColor: '#f3f4f6', padding: '14px' }}>
        <Text onClick={closeDoc} style={{ display: 'block', color: '#4F46E5', marginBottom: '12px' }}>‹ 返回</Text>
        <Text style={{ display: 'block', fontSize: '16px', fontWeight: 'bold', marginBottom: '10px' }}>{contentTitle}</Text>
        <ScrollView scrollY style={{ height: '82vh', backgroundColor: '#fff', borderRadius: '12px', padding: '12px', border: '1px solid #e5e7eb' }}>
          <Text style={{ fontSize: '13px', fontFamily: 'monospace', whiteSpace: 'pre-wrap', color: '#374151' }}>{content}</Text>
        </ScrollView>
      </View>
    );
  }

  return (
    <View style={{ minHeight: '100vh', backgroundColor: '#f3f4f6', padding: '14px' }}>
      <View style={{ backgroundColor: '#4F46E5', color: '#fff', borderRadius: '12px', padding: '16px', marginBottom: '12px' }}>
        <Text style={{ display: 'block', fontSize: '20px', fontWeight: 'bold' }}>引擎记忆（只读）</Text>
        <Text style={{ display: 'block', fontSize: '12px', color: '#c7d2fe', marginTop: '4px' }}>
          DeepTutor 全局长期记忆 · 共享 · 仅供查看
        </Text>
      </View>

      {loading && <Text style={{ display: 'block', textAlign: 'center', color: '#9ca3af', padding: '24px' }}>加载中...</Text>}

      {disabled && (
        <View style={{ textAlign: 'center', padding: '40px 24px' }}>
          <Text style={{ display: 'block', fontSize: '32px' }}>🔒</Text>
          <Text style={{ display: 'block', color: '#9ca3af', marginTop: '8px' }}>引擎记忆查看未启用</Text>
        </View>
      )}

      {error !== '' && <Text style={{ display: 'block', textAlign: 'center', color: '#ef4444', padding: '8px' }}>{error}</Text>}

      {!loading && !disabled && docs.map((d) => (
        <View
          key={`${d.layer}/${d.key}`}
          style={{ backgroundColor: '#fff', border: '1px solid #e5e7eb', borderRadius: '12px', padding: '13px', marginBottom: '10px' }}
          onClick={() => openDoc(d.layer, d.key)}
        >
          <Text style={{ padding: '2px 8px', borderRadius: '5px', fontSize: '11px', backgroundColor: '#ede9fe', color: '#5b21b6' }}>{d.layer}</Text>
          <Text style={{ fontSize: '15px', fontWeight: '600', marginLeft: '8px' }}>{d.key}</Text>
        </View>
      ))}
    </View>
  );
}
