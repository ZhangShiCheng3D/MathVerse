import { useState } from 'react';
import { View, Text, Input, Button } from '@tarojs/components';
import { useVisualizeStore } from '../../stores/visualize';
import { useUserStore } from '../../stores/user';

export default function VisualizePage() {
  const { loading, result, error, analyzePhoto } = useVisualizeStore();
  const user = useUserStore((s) => s.user);
  const stage = user?.current_stage || 'college';
  const [question, setQuestion] = useState('请分析图片中的几何图形');

  return (
    <View style={{ minHeight: '100vh', backgroundColor: '#f3f4f6', padding: '14px' }}>
      <View style={{ backgroundColor: '#4F46E5', color: '#fff', borderRadius: '12px', padding: '16px', marginBottom: '12px' }}>
        <Text style={{ display: 'block', fontSize: '20px', fontWeight: 'bold' }}>几何可视化</Text>
        <Text style={{ display: 'block', fontSize: '12px', color: '#c7d2fe', marginTop: '4px' }}>
          拍下几何题，AI 解析为 GeoGebra 作图命令
        </Text>
      </View>

      <Input
        value={question}
        onInput={(e) => setQuestion(e.detail.value)}
        placeholder="描述你想分析什么"
        style={{ backgroundColor: '#fff', borderRadius: '10px', padding: '10px', fontSize: '14px', border: '1px solid #e5e7eb', marginBottom: '10px' }}
      />

      <Button
        loading={loading}
        style={{ backgroundColor: '#4F46E5', color: '#fff', borderRadius: '9999px', fontSize: '14px', marginBottom: '12px' }}
        onClick={() => analyzePhoto(question, stage)}
      >
        📷 拍照 / 选图分析
      </Button>

      {error !== '' && <Text style={{ display: 'block', textAlign: 'center', color: '#ef4444', padding: '8px' }}>{error}</Text>}

      {result && (
        <View style={{ backgroundColor: '#fff', border: '1px solid #e5e7eb', borderRadius: '12px', padding: '13px' }}>
          {!result.has_image && (
            <Text style={{ display: 'block', color: '#9ca3af' }}>未检测到图形内容</Text>
          )}
          {result.has_image && (
            <>
              <Text style={{ display: 'block', fontWeight: '600', marginBottom: '6px' }}>
                作图命令（{result.ggb_commands.length}）
              </Text>
              {result.ggb_commands.map((c, i) => (
                <Text key={i} style={{ display: 'block', fontFamily: 'monospace', fontSize: '13px', color: '#374151', padding: '2px 0' }}>
                  {typeof c === 'string' ? c : JSON.stringify(c)}
                </Text>
              ))}
              {result.ggb_script && (
                <Text style={{ display: 'block', fontSize: '12px', color: '#9ca3af', marginTop: '8px', whiteSpace: 'pre-wrap' }}>
                  {result.ggb_script}
                </Text>
              )}
            </>
          )}
        </View>
      )}
    </View>
  );
}
