import { useEffect, useState } from 'react';
import { View, Text, Input, Button, ScrollView } from '@tarojs/components';
import Taro from '@tarojs/taro';
import { useBookStore } from '../../stores/book';

function blockText(b: any): string {
  if (typeof b === 'string') return b;
  if (b && typeof b === 'object') {
    for (const k of ['content', 'text', 'markdown', 'body']) {
      if (typeof b[k] === 'string' && b[k].trim()) return b[k];
    }
  }
  try { return JSON.stringify(b); } catch { return String(b); }
}

export default function BookPage() {
  const { list, loading, busy, error, detail, page, fetchList, create, generate, open, openPage, closePage, closeDetail, remove } = useBookStore();
  const [intent, setIntent] = useState('');

  useEffect(() => {
    fetchList();
  }, []);

  // ── single page view ──
  if (page) {
    return (
      <View style={{ minHeight: '100vh', backgroundColor: '#f3f4f6', padding: '14px' }}>
        <Text onClick={closePage} style={{ display: 'block', color: '#4F46E5', marginBottom: '12px' }}>‹ 返回目录</Text>
        <Text style={{ display: 'block', fontSize: '18px', fontWeight: 'bold', marginBottom: '10px' }}>{page.title || '页面'}</Text>
        <ScrollView scrollY style={{ height: '82vh' }}>
          {(page.blocks || []).map((b: any, i: number) => (
            <View key={i} style={{ backgroundColor: '#fff', borderRadius: '10px', padding: '12px', marginBottom: '10px', border: '1px solid #e5e7eb' }}>
              <Text style={{ fontSize: '14px', whiteSpace: 'pre-wrap', color: '#374151' }}>{blockText(b)}</Text>
            </View>
          ))}
          {(!page.blocks || page.blocks.length === 0) && (
            <Text style={{ display: 'block', color: '#9ca3af' }}>该页暂无内容（可能尚未编译）</Text>
          )}
        </ScrollView>
      </View>
    );
  }

  // ── book detail (page list) ──
  if (detail) {
    return (
      <View style={{ minHeight: '100vh', backgroundColor: '#f3f4f6', padding: '14px' }}>
        <Text onClick={closeDetail} style={{ display: 'block', color: '#4F46E5', marginBottom: '12px' }}>‹ 返回书架</Text>
        <Text style={{ display: 'block', fontSize: '18px', fontWeight: 'bold', marginBottom: '12px' }}>{detail.book.title || 'AI 教材'}</Text>
        {detail.pages.length === 0 && (
          <Text style={{ display: 'block', color: '#9ca3af' }}>还没有页面，点「生成」后会编译出章节</Text>
        )}
        {detail.pages.map((p: any, i: number) => (
          <View
            key={p.id || i}
            style={{ backgroundColor: '#fff', border: '1px solid #e5e7eb', borderRadius: '12px', padding: '13px', marginBottom: '10px' }}
            onClick={() => openPage(p)}
          >
            <Text style={{ fontSize: '15px', fontWeight: '600' }}>{p.title || `第 ${i + 1} 页`}</Text>
            {p.status ? <Text style={{ display: 'block', fontSize: '11px', color: '#9ca3af', marginTop: '2px' }}>{p.status}</Text> : null}
          </View>
        ))}
      </View>
    );
  }

  // ── book shelf (list + create) ──
  return (
    <View style={{ minHeight: '100vh', backgroundColor: '#f3f4f6', padding: '14px' }}>
      <View style={{ backgroundColor: '#4F46E5', color: '#fff', borderRadius: '12px', padding: '16px', marginBottom: '12px' }}>
        <Text style={{ display: 'block', fontSize: '20px', fontWeight: 'bold' }}>AI 教材</Text>
        <Text style={{ display: 'block', fontSize: '12px', color: '#c7d2fe', marginTop: '4px' }}>用一句话生成一本结构化学习教材</Text>
      </View>

      <View style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
        <Input
          value={intent}
          onInput={(e) => setIntent(e.detail.value)}
          placeholder="例如：帮我讲透线性代数特征值"
          style={{ flex: 1, backgroundColor: '#fff', borderRadius: '10px', padding: '10px', fontSize: '14px', border: '1px solid #e5e7eb' }}
        />
        <Button
          loading={busy}
          style={{ backgroundColor: '#4F46E5', color: '#fff', borderRadius: '10px', fontSize: '14px' }}
          onClick={async () => {
            if (!intent.trim()) return;
            try { await create(intent.trim()); setIntent(''); Taro.showToast({ title: '已创建，点「生成」', icon: 'none' }); }
            catch (e: any) { Taro.showToast({ title: e?.message || '创建失败', icon: 'none' }); }
          }}
        >
          创建
        </Button>
      </View>

      {loading && <Text style={{ display: 'block', textAlign: 'center', color: '#9ca3af', padding: '24px' }}>加载中...</Text>}
      {error !== '' && <Text style={{ display: 'block', textAlign: 'center', color: '#ef4444', padding: '8px' }}>{error}</Text>}

      {!loading && list.length === 0 && (
        <View style={{ textAlign: 'center', padding: '40px 24px' }}>
          <Text style={{ display: 'block', fontSize: '32px' }}>📕</Text>
          <Text style={{ display: 'block', color: '#9ca3af', marginTop: '8px' }}>还没有教材，输入主题创建一本</Text>
        </View>
      )}

      {list.map((b) => (
        <View key={b.id} style={{ backgroundColor: '#fff', border: '1px solid #e5e7eb', borderRadius: '12px', padding: '13px', marginBottom: '11px' }}>
          <Text style={{ display: 'block', fontSize: '15px', fontWeight: '600', marginBottom: '8px' }}>{b.title || b.id}</Text>
          <View style={{ display: 'flex', gap: '8px' }}>
            <Button size="mini" style={{ backgroundColor: '#eef2ff', color: '#4338ca', fontSize: '12px' }} onClick={() => open(b.id)}>打开</Button>
            <Button size="mini" loading={busy} style={{ backgroundColor: '#10b981', color: '#fff', fontSize: '12px' }} onClick={() => generate(b.id)}>生成</Button>
            <Button size="mini" style={{ backgroundColor: '#fee2e2', color: '#b91c1c', fontSize: '12px' }} onClick={() => remove(b.id)}>删除</Button>
          </View>
        </View>
      ))}
    </View>
  );
}
