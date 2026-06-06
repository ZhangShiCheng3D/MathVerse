import { useEffect, useState } from 'react';
import { View, Text, Input, Button } from '@tarojs/components';
import Taro from '@tarojs/taro';
import { useNotebookStore } from '../../stores/notebook';

export default function NotebookPage() {
  const { list, loading, busy, error, fetchList, create, remove } = useNotebookStore();
  const [name, setName] = useState('');

  useEffect(() => {
    fetchList();
  }, []);

  const onCreate = async () => {
    if (!name.trim()) return;
    try {
      await create(name.trim());
      setName('');
    } catch (e: any) {
      Taro.showToast({ title: e?.message || '创建失败', icon: 'none' });
    }
  };

  return (
    <View style={{ minHeight: '100vh', backgroundColor: '#f3f4f6', padding: '14px' }}>
      <View style={{ backgroundColor: '#4F46E5', color: '#fff', borderRadius: '12px', padding: '16px', marginBottom: '12px' }}>
        <Text style={{ display: 'block', fontSize: '20px', fontWeight: 'bold' }}>笔记本</Text>
        <Text style={{ display: 'block', fontSize: '12px', color: '#c7d2fe', marginTop: '4px' }}>
          收藏解题、研究与对话，AI 自动生成摘要
        </Text>
      </View>

      <View style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
        <Input
          value={name}
          onInput={(e) => setName(e.detail.value)}
          placeholder="新建笔记本名称"
          style={{ flex: 1, backgroundColor: '#fff', borderRadius: '10px', padding: '10px', fontSize: '14px', border: '1px solid #e5e7eb' }}
        />
        <Button loading={busy} style={{ backgroundColor: '#4F46E5', color: '#fff', borderRadius: '10px', fontSize: '14px' }} onClick={onCreate}>
          新建
        </Button>
      </View>

      {loading && <Text style={{ display: 'block', textAlign: 'center', color: '#9ca3af', padding: '24px' }}>加载中...</Text>}
      {error !== '' && <Text style={{ display: 'block', textAlign: 'center', color: '#ef4444', padding: '8px' }}>{error}</Text>}

      {!loading && list.length === 0 && (
        <View style={{ textAlign: 'center', padding: '40px 24px' }}>
          <Text style={{ display: 'block', fontSize: '32px' }}>📓</Text>
          <Text style={{ display: 'block', color: '#9ca3af', marginTop: '8px' }}>还没有笔记本，新建一个吧</Text>
        </View>
      )}

      {list.map((nb) => (
        <View key={nb.id} style={{ backgroundColor: '#fff', border: '1px solid #e5e7eb', borderRadius: '12px', padding: '13px', marginBottom: '11px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Text style={{ fontSize: '15px', fontWeight: '600' }}>{nb.name || nb.id}</Text>
          <Button size="mini" style={{ backgroundColor: '#fee2e2', color: '#b91c1c', fontSize: '12px' }} onClick={() => remove(nb.id)}>
            删除
          </Button>
        </View>
      ))}
    </View>
  );
}
