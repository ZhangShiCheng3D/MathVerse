import { useEffect, useState } from 'react';
import { View, Text, Button } from '@tarojs/components';
import Taro from '@tarojs/taro';
import { request } from '../../services/api';

interface Task {
  kp_id: string;
  name: string;
  chapter: string;
  task_type: string;
  reason: string;
}

export default function PlanPage() {
  const [date, setDate] = useState('');
  const [tasks, setTasks] = useState<Task[] | null>(null);

  useEffect(() => {
    request<{ date: string; tasks: Task[] }>('/api/me/plan/today')
      .then((d) => { setDate(d.date); setTasks(d.tasks || []); })
      .catch(() => setTasks([]));
  }, []);

  return (
    <View style={{ minHeight: '100vh', backgroundColor: '#f3f4f6', padding: '14px' }}>
      <View style={{ backgroundColor: '#4F46E5', color: '#fff', borderRadius: '12px', padding: '16px', marginBottom: '12px' }}>
        <Text style={{ display: 'block', fontSize: '13px', color: '#c7d2fe' }}>{date} · 今日任务</Text>
        <Text style={{ display: 'block', fontSize: '22px', fontWeight: 'bold', marginTop: '2px' }}>
          {tasks === null ? '生成中…' : `${tasks.length} 个薄弱知识点`}
        </Text>
        <Text style={{ display: 'block', fontSize: '12px', color: '#c7d2fe' }}>按掌握度 + 高频考点排序</Text>
      </View>

      {tasks === null && (
        <Text style={{ display: 'block', textAlign: 'center', color: '#9ca3af', padding: '24px' }}>加载中...</Text>
      )}

      {tasks && tasks.length === 0 && (
        <View style={{ textAlign: 'center', padding: '48px 24px' }}>
          <Text style={{ display: 'block', fontSize: '32px' }}>🎉</Text>
          <Text style={{ display: 'block', color: '#9ca3af', marginTop: '8px' }}>太棒了！暂无薄弱点，继续保持</Text>
        </View>
      )}

      {tasks && tasks.map((t) => {
        const isLearn = t.task_type === 'learn';
        return (
          <View key={t.kp_id} style={{ backgroundColor: '#fff', border: '1px solid #e5e7eb', borderRadius: '12px', padding: '13px', marginBottom: '11px' }}>
            <View style={{ display: 'flex', gap: '5px', marginBottom: '6px' }}>
              <Text style={{
                padding: '2px 8px', borderRadius: '5px', fontSize: '11px',
                backgroundColor: isLearn ? '#fef9c3' : '#dbeafe',
                color: isLearn ? '#854d0e' : '#1e40af',
              }}>
                {isLearn ? '新学' : '复习'}
              </Text>
            </View>
            <Text style={{ display: 'block', fontSize: '15px', fontWeight: '600' }}>{t.name}</Text>
            <Text style={{ display: 'block', fontSize: '12px', color: '#9ca3af', marginTop: '2px' }}>
              {t.chapter} · {t.reason}
            </Text>
          </View>
        );
      })}

      {tasks && tasks.length > 0 && (
        <Button
          style={{ backgroundColor: '#4F46E5', color: '#fff', borderRadius: '9999px', fontSize: '14px', marginTop: '6px' }}
          onClick={() => Taro.switchTab({ url: '/pages/learn/index' })}
        >
          去学习页 →
        </Button>
      )}
    </View>
  );
}
