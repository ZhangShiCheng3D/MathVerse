import { useState } from 'react';
import { View, Text, Textarea, Button, ScrollView } from '@tarojs/components';
import Taro from '@tarojs/taro';
import { useSolveStore } from '../../stores/solve';
import { useUserStore } from '../../stores/user';

export default function SolvePage() {
  const {
    question, setQuestion, isSolving, result,
    expandedLayer, expandLayer, askWhy,
    whyExplanation, solveStreaming, solveByPhoto, reset,
    addToMistakes, addedToMistakes, streamingText, isStreaming,
  } = useSolveStore();
  const user = useUserStore((s) => s.user);
  const [error, setError] = useState('');

  const handleAddMistake = async () => {
    try {
      await addToMistakes();
      Taro.showToast({ title: '已加入错题本', icon: 'success' });
    } catch (err: any) {
      const msg = err?.message === 'Authentication required' ? '请先登录' : '加入失败';
      Taro.showToast({ title: msg, icon: 'none' });
    }
  };

  const handleSolve = async () => {
    setError('');
    try {
      await solveStreaming(user?.current_stage || 'college');
    } catch (err: any) {
      setError(err.message || '解题失败');
    }
  };

  // Streaming prose ends with a ```json``` block we rebuild into the layered view —
  // hide that raw block from the live typing display.
  const liveText = streamingText.split('```')[0].trim();

  const handlePhoto = async () => {
    setError('');
    try {
      await solveByPhoto(user?.current_stage || 'college');
    } catch (err: any) {
      setError(err.message || '拍照解题失败');
    }
  };

  return (
    <View className='p-4 min-h-screen bg-white'>
      {/* Input Area */}
      <View className='mb-4'>
        <Textarea
          className='w-full p-4 border rounded-xl text-base'
          style={{ minHeight: '120px' }}
          placeholder='输入题目，如"求极限 lim(x→0) sin(x)/x"'
          value={question}
          onInput={(e) => setQuestion(e.detail.value)}
        />
        <View className='flex' style={{ gap: '8px', marginTop: '8px' }}>
          <Button
            className='flex-1'
            style={{ backgroundColor: '#4F46E5', color: '#fff', borderRadius: '9999px' }}
            onClick={handleSolve}
            loading={isSolving}
          >
            {isSolving ? 'AI思考中...' : '解答'}
          </Button>
          <Button
            style={{ padding: '0 16px', border: '1px solid #4F46E5', color: '#4F46E5', borderRadius: '9999px', backgroundColor: '#fff' }}
            onClick={handlePhoto}
            disabled={isSolving}
          >
            📷 拍照
          </Button>
          {result && (
            <Button
              style={{ padding: '0 16px', border: '1px solid #ddd', borderRadius: '9999px', backgroundColor: '#fff' }}
              onClick={reset}
            >
              新题目
            </Button>
          )}
        </View>
        {error && <Text style={{ color: '#ef4444', fontSize: '14px', marginTop: '4px' }}>{error}</Text>}
      </View>

      {/* Streaming / loading */}
      {isSolving && !result && (
        <View style={{ padding: '16px', backgroundColor: '#f9fafb', borderRadius: '12px', marginBottom: '16px' }}>
          {liveText ? (
            <Text style={{ fontSize: '15px', lineHeight: '1.8', color: '#374151', whiteSpace: 'pre-wrap' }}>
              {liveText}
              <Text style={{ color: '#4F46E5' }}>▍</Text>
            </Text>
          ) : (
            <Text style={{ color: '#9ca3af' }}>{isStreaming ? 'AI 正在思考…' : 'AI 正在分析你的题目...'}</Text>
          )}
        </View>
      )}

      {/* Result */}
      {result && (
        <ScrollView scrollY style={{ flex: 1 }}>
          {/* Layer 1: Answer */}
          <View style={{ padding: '16px', backgroundColor: '#f0fdf4', borderRadius: '12px', marginBottom: '16px' }}>
            <Text style={{ fontSize: '18px', fontWeight: 'bold', color: '#166534' }}>
              答案：{result.answer}
            </Text>
            {expandedLayer === 1 && (
              <Button
                style={{ marginTop: '8px', color: '#4F46E5', fontSize: '14px', backgroundColor: 'transparent', padding: 0 }}
                onClick={() => expandLayer(2)}
              >
                查看解题步骤 →
              </Button>
            )}
          </View>

          {/* Layer 2: Steps */}
          {expandedLayer >= 2 && result.steps.map((step, i) => (
            <View key={i} style={{ padding: '16px', border: '1px solid #e5e7eb', borderRadius: '12px', marginBottom: '12px' }}>
              <Text style={{ fontWeight: 'bold', color: '#312e81' }}>
                【Step {step.index}】{step.title}
              </Text>
              <Text style={{ display: 'block', marginTop: '4px', color: '#374151' }}>
                {step.content}
              </Text>
              <Text style={{ display: 'block', marginTop: '8px', fontSize: '14px', color: '#6b7280' }}>
                WHY: {step.why}
              </Text>
              <Button
                style={{ marginTop: '8px', fontSize: '12px', color: '#6366f1', backgroundColor: 'transparent', padding: 0 }}
                onClick={() => askWhy(step.index, step.content)}
              >
                追问"为什么" →
              </Button>
              {whyExplanation && (
                <View style={{ marginTop: '8px', padding: '12px', backgroundColor: '#eef2ff', borderRadius: '8px' }}>
                  <Text style={{ fontSize: '14px', color: '#3730a3' }}>{whyExplanation}</Text>
                </View>
              )}
            </View>
          ))}

          {/* Layer 3: Summary */}
          {expandedLayer >= 3 && (
            <View style={{ padding: '16px', backgroundColor: '#f9fafb', borderRadius: '12px', marginBottom: '16px' }}>
              <Text style={{ fontWeight: 'bold', marginBottom: '8px' }}>知识点</Text>
              <View style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginBottom: '12px' }}>
                {result.knowledge_points.map((kp, i) => (
                  <Text key={i} style={{
                    padding: '2px 8px',
                    backgroundColor: '#e0e7ff',
                    color: '#4338ca',
                    fontSize: '12px',
                    borderRadius: '4px',
                  }}>
                    {kp}
                  </Text>
                ))}
              </View>
              <Text style={{ fontWeight: 'bold', marginBottom: '4px' }}>常见错误</Text>
              {result.common_mistakes.map((m, i) => (
                <Text key={i} style={{ display: 'block', fontSize: '14px', color: '#dc2626' }}>
                  ⚠ {m}
                </Text>
              ))}
            </View>
          )}

          {/* Layer Navigation */}
          <View style={{ display: 'flex', gap: '8px', marginBottom: '32px' }}>
            {expandedLayer > 1 && (
              <Button style={{ fontSize: '14px' }} onClick={() => expandLayer((expandedLayer - 1) as 1 | 2 | 3)}>
                ← 收起
              </Button>
            )}
            {expandedLayer < 3 && (
              <Button
                style={{ fontSize: '14px', color: '#4F46E5' }}
                onClick={() => expandLayer((expandedLayer + 1) as 1 | 2 | 3)}
              >
                展开更多 →
              </Button>
            )}
          </View>

          {/* Add to mistake notebook — only for text questions (photo solve has no question text) */}
          {question.trim() && (
            <Button
              style={{
                marginBottom: '32px',
                backgroundColor: addedToMistakes ? '#f3f4f6' : '#fff',
                color: addedToMistakes ? '#9ca3af' : '#4F46E5',
                border: addedToMistakes ? '1px solid #e5e7eb' : '1px solid #4F46E5',
                borderRadius: '9999px',
                fontSize: '14px',
              }}
              disabled={addedToMistakes}
              onClick={handleAddMistake}
            >
              {addedToMistakes ? '✓ 已加入错题本' : '📕 加入错题本'}
            </Button>
          )}
        </ScrollView>
      )}
    </View>
  );
}
