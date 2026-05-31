import { useEffect } from 'react';
import { View, Text, ScrollView, Button } from '@tarojs/components';
import { useLearnStore } from '../../stores/learn';

const STAGES = [
  { id: 'primary-low', label: '小学低段' },
  { id: 'junior', label: '初中' },
  { id: 'senior', label: '高中' },
  { id: 'college', label: '大学' },
  { id: 'kaoyan', label: '考研' },
];

const masteryColor = (m: number) => {
  if (m >= 0.8) return '#22c55e';
  if (m >= 0.5) return '#eab308';
  if (m > 0) return '#f97316';
  return '#d1d5db';
};

export default function LearnPage() {
  const {
    stage, setStage, kgData, selectedKp, lecture, activeTab,
    isLoading, fetchKg, selectKp, fetchLecture,
  } = useLearnStore();

  useEffect(() => {
    fetchKg();
  }, [stage]);

  if (!selectedKp) {
    return (
      <View style={{ minHeight: '100vh', backgroundColor: '#fff' }}>
        {/* Stage Selector */}
        <ScrollView scrollX style={{ display: 'flex', padding: '8px', gap: '4px', borderBottom: '1px solid #e5e7eb' }}>
          {STAGES.map((s) => (
            <Button
              key={s.id}
              style={{
                padding: '4px 12px',
                fontSize: '14px',
                borderRadius: '9999px',
                whiteSpace: 'nowrap',
                backgroundColor: stage === s.id ? '#4F46E5' : '#f3f4f6',
                color: stage === s.id ? '#fff' : '#374151',
              }}
              onClick={() => setStage(s.id)}
            >
              {s.label}
            </Button>
          ))}
        </ScrollView>

        {/* Subject Cards */}
        <ScrollView style={{ padding: '16px' }}>
          {kgData?.map((subject) => (
            <View key={subject.id} style={{ marginBottom: '16px' }}>
              <Text style={{ fontSize: '18px', fontWeight: 'bold', marginBottom: '8px', display: 'block' }}>
                {subject.name}
              </Text>
              {subject.chapters.map((ch) => (
                <View key={ch.id} style={{ marginBottom: '12px', padding: '12px', border: '1px solid #e5e7eb', borderRadius: '8px' }}>
                  <Text style={{ fontWeight: '600', fontSize: '14px', color: '#374151' }}>
                    {ch.name}
                    <Text style={{ color: ch.frequency === 'high' ? '#ef4444' : '#6b7280', fontSize: '12px', marginLeft: '8px' }}>
                      {ch.frequency === 'high' ? '高频' : ''}
                    </Text>
                  </Text>
                  <View style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '8px' }}>
                    {ch.topics.map((topic, i) => (
                      <View
                        key={i}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px',
                          padding: '4px 8px',
                          backgroundColor: '#f9fafb',
                          borderRadius: '4px',
                        }}
                        onClick={() => selectKp(topic)}
                      >
                        <View style={{
                          width: '8px',
                          height: '8px',
                          borderRadius: '50%',
                          backgroundColor: masteryColor(topic.mastery || 0),
                        }} />
                        <Text style={{ fontSize: '12px' }}>{topic.name}</Text>
                        <Text style={{ fontSize: '10px', color: '#9ca3af' }}>
                          {'★'.repeat(topic.difficulty)}{'☆'.repeat(5 - topic.difficulty)}
                        </Text>
                      </View>
                    ))}
                  </View>
                </View>
              ))}
            </View>
          ))}
          {isLoading && <Text style={{ color: '#9ca3af', textAlign: 'center', display: 'block' }}>加载中...</Text>}
        </ScrollView>
      </View>
    );
  }

  // KP Detail Card
  return (
    <ScrollView style={{ padding: '16px', minHeight: '100vh', backgroundColor: '#fff' }}>
      <Button
        style={{ color: '#4F46E5', fontSize: '14px', marginBottom: '16px', backgroundColor: 'transparent', padding: 0, textAlign: 'left' }}
        onClick={() => useLearnStore.setState({ selectedKp: null })}
      >
        ← 返回知识地图
      </Button>

      <View style={{ padding: '16px', border: '1px solid #e5e7eb', borderRadius: '12px', marginBottom: '16px' }}>
        <Text style={{ fontSize: '20px', fontWeight: 'bold' }}>{selectedKp.name}</Text>
        <Text style={{ display: 'block', fontSize: '14px', color: '#6b7280', marginTop: '4px' }}>
          难度：{'★'.repeat(selectedKp.difficulty)}{'☆'.repeat(5 - selectedKp.difficulty)}
        </Text>
        {selectedKp.mastery !== undefined && (
          <Text style={{ display: 'block', fontSize: '14px', marginTop: '4px' }}>
            掌握度：<Text style={{ fontWeight: 'bold', color: '#4F46E5' }}>
              {Math.round(selectedKp.mastery * 100)}%
            </Text>
          </Text>
        )}
      </View>

      {/* Tab buttons */}
      <View style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
        <Button
          style={{
            flex: 1,
            borderRadius: '9999px',
            backgroundColor: activeTab === 'lecture' ? '#4F46E5' : '#fff',
            color: activeTab === 'lecture' ? '#fff' : '#374151',
            border: activeTab === 'lecture' ? 'none' : '1px solid #d1d5db',
          }}
          onClick={() => fetchLecture(selectedKp.name, selectedKp.id)}
        >
          讲解
        </Button>
        <Button
          style={{
            flex: 1,
            borderRadius: '9999px',
            backgroundColor: activeTab === 'exercise' ? '#4F46E5' : '#fff',
            color: activeTab === 'exercise' ? '#fff' : '#374151',
            border: activeTab === 'exercise' ? 'none' : '1px solid #d1d5db',
          }}
          onClick={() => useLearnStore.setState({ activeTab: 'exercise' })}
        >
          练习
        </Button>
      </View>

      {/* Content */}
      {activeTab === 'lecture' && (
        <View style={{ padding: '16px', backgroundColor: '#f9fafb', borderRadius: '12px' }}>
          {isLoading ? (
            <Text style={{ color: '#9ca3af' }}>AI正在备课...</Text>
          ) : lecture ? (
            <Text style={{ fontSize: '16px', lineHeight: '1.8', whiteSpace: 'pre-wrap' }}>
              {lecture}
            </Text>
          ) : (
            <Text style={{ color: '#9ca3af' }}>点击"讲解"开始学习</Text>
          )}
        </View>
      )}

      {activeTab === 'exercise' && (
        <View style={{ padding: '16px' }}>
          <Text style={{ color: '#9ca3af' }}>练习功能即将上线</Text>
        </View>
      )}
    </ScrollView>
  );
}
