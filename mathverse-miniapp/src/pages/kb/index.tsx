import { useEffect } from 'react';
import { View, Text, Button } from '@tarojs/components';
import Taro from '@tarojs/taro';
import { useKbStore } from '../../stores/kb';
import { useUserStore } from '../../stores/user';

export default function KbPage() {
  const { list, loading, busy, error, fetchList, seedCurriculum, remove } = useKbStore();
  const user = useUserStore((s) => s.user);
  const stage = user?.current_stage || 'college';

  useEffect(() => {
    fetchList();
  }, []);

  const onSeed = async () => {
    try {
      await seedCurriculum(stage);
      Taro.showToast({ title: '课程种子库已生成', icon: 'success' });
    } catch (e: any) {
      Taro.showToast({ title: e?.message || '生成失败', icon: 'none' });
    }
  };

  const onDelete = async (name: string) => {
    try {
      await remove(name);
    } catch (e: any) {
      Taro.showToast({ title: e?.message || '删除失败', icon: 'none' });
    }
  };

  return (
    <View style={{ minHeight: '100vh', backgroundColor: '#f3f4f6', padding: '14px' }}>
      <View style={{ backgroundColor: '#4F46E5', color: '#fff', borderRadius: '12px', padding: '16px', marginBottom: '12px' }}>
        <Text style={{ display: 'block', fontSize: '20px', fontWeight: 'bold' }}>知识库 (RAG)</Text>
        <Text style={{ display: 'block', fontSize: '12px', color: '#c7d2fe', marginTop: '4px' }}>
          解题时可基于知识库做有据可依的溯源回答
        </Text>
      </View>

      <Button
        loading={busy}
        style={{ backgroundColor: '#10b981', color: '#fff', borderRadius: '9999px', fontSize: '14px', marginBottom: '12px' }}
        onClick={onSeed}
      >
        用「{stage}」课程图谱生成种子库
      </Button>

      {loading && <Text style={{ display: 'block', textAlign: 'center', color: '#9ca3af', padding: '24px' }}>加载中...</Text>}
      {error !== '' && <Text style={{ display: 'block', textAlign: 'center', color: '#ef4444', padding: '12px' }}>{error}</Text>}

      {!loading && list.length === 0 && (
        <View style={{ textAlign: 'center', padding: '40px 24px' }}>
          <Text style={{ display: 'block', fontSize: '32px' }}>📚</Text>
          <Text style={{ display: 'block', color: '#9ca3af', marginTop: '8px' }}>还没有知识库，先生成课程种子库吧</Text>
        </View>
      )}

      {list.map((kb) => (
        <View key={(kb.shared ? 'c:' : 'u:') + kb.name} style={{ backgroundColor: '#fff', border: '1px solid #e5e7eb', borderRadius: '12px', padding: '13px', marginBottom: '11px' }}>
          <View style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Text style={{ fontSize: '15px', fontWeight: '600' }}>{kb.name}</Text>
            {kb.shared && (
              <Text style={{ padding: '2px 8px', borderRadius: '5px', fontSize: '11px', backgroundColor: '#dbeafe', color: '#1e40af' }}>共享课程</Text>
            )}
            {kb.status && (
              <Text style={{ fontSize: '11px', color: '#9ca3af' }}>{kb.status}</Text>
            )}
          </View>
          {!kb.read_only && (
            <Button
              size="mini"
              style={{ marginTop: '8px', backgroundColor: '#fee2e2', color: '#b91c1c', fontSize: '12px' }}
              onClick={() => onDelete(kb.name)}
            >
              删除
            </Button>
          )}
        </View>
      ))}
    </View>
  );
}
