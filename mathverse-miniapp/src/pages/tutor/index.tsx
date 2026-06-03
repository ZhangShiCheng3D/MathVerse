import { useState } from 'react';
import { View, Text, Textarea, Button, ScrollView, Input } from '@tarojs/components';
import { useTutorStore, Capability } from '../../stores/tutor';
import { useUserStore } from '../../stores/user';

const CAPS: { key: Capability; label: string }[] = [
  { key: 'chat', label: '对话' },
  { key: 'solve', label: '解题' },
  { key: 'research', label: '深度研究' },
  { key: 'visualize', label: '可视化' },
];

export default function TutorPage() {
  const { capability, messages, streaming, isRunning, ask, error, setCapability, send, regenerate, reply } = useTutorStore();
  const user = useUserStore((s) => s.user);
  const stage = user?.current_stage || 'college';
  const [draft, setDraft] = useState('');
  const [replyText, setReplyText] = useState('');

  const onSend = () => {
    if (!draft.trim()) return;
    send(draft, stage);
    setDraft('');
  };

  const onReply = () => {
    reply(replyText);
    setReplyText('');
  };

  const canRegen = !isRunning && messages.some((m) => m.role === 'assistant');

  return (
    <View style={{ display: 'flex', flexDirection: 'column', height: '100vh', backgroundColor: '#f3f4f6' }}>
      {/* capability switcher */}
      <View style={{ display: 'flex', gap: '6px', padding: '10px', backgroundColor: '#fff', borderBottom: '1px solid #e5e7eb' }}>
        {CAPS.map((c) => (
          <Text
            key={c.key}
            onClick={() => setCapability(c.key)}
            style={{
              padding: '4px 12px', borderRadius: '9999px', fontSize: '13px',
              backgroundColor: capability === c.key ? '#4F46E5' : '#f3f4f6',
              color: capability === c.key ? '#fff' : '#6b7280',
            }}
          >
            {c.label}
          </Text>
        ))}
      </View>

      {/* conversation */}
      <ScrollView scrollY style={{ flex: 1, padding: '12px' }}>
        {messages.length === 0 && !streaming && (
          <View style={{ textAlign: 'center', padding: '48px 24px' }}>
            <Text style={{ display: 'block', fontSize: '32px' }}>🤖</Text>
            <Text style={{ display: 'block', color: '#9ca3af', marginTop: '8px' }}>
              我是你的 AI 数学导师，支持多轮对话、深度研究与可视化
            </Text>
          </View>
        )}
        {messages.map((m, i) => (
          <View
            key={i}
            style={{
              maxWidth: '85%', marginBottom: '10px', padding: '10px 12px', borderRadius: '12px',
              alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
              marginLeft: m.role === 'user' ? 'auto' : '0',
              backgroundColor: m.role === 'user' ? '#4F46E5' : '#fff',
              color: m.role === 'user' ? '#fff' : '#111827',
              border: m.role === 'user' ? 'none' : '1px solid #e5e7eb',
            }}
          >
            <Text style={{ fontSize: '14px', whiteSpace: 'pre-wrap' }}>{m.content}</Text>
          </View>
        ))}
        {streaming !== '' && (
          <View style={{ maxWidth: '85%', marginBottom: '10px', padding: '10px 12px', borderRadius: '12px', backgroundColor: '#fff', border: '1px solid #e5e7eb' }}>
            <Text style={{ fontSize: '14px', whiteSpace: 'pre-wrap' }}>{streaming}</Text>
          </View>
        )}
        {error !== '' && (
          <Text style={{ display: 'block', textAlign: 'center', color: '#ef4444', fontSize: '13px', padding: '8px' }}>{error}</Text>
        )}
      </ScrollView>

      {/* ask_user interactive prompt */}
      {ask.pending && (
        <View style={{ padding: '10px 12px', backgroundColor: '#fffbeb', borderTop: '1px solid #fde68a' }}>
          <Text style={{ display: 'block', fontSize: '13px', color: '#854d0e', marginBottom: '6px' }}>导师追问：{ask.question}</Text>
          <View style={{ display: 'flex', gap: '8px' }}>
            <Input
              value={replyText}
              onInput={(e) => setReplyText(e.detail.value)}
              placeholder="输入你的回答"
              style={{ flex: 1, backgroundColor: '#fff', borderRadius: '8px', padding: '6px 10px', fontSize: '14px', border: '1px solid #e5e7eb' }}
            />
            <Button size="mini" style={{ backgroundColor: '#f59e0b', color: '#fff' }} onClick={onReply}>回复</Button>
          </View>
        </View>
      )}

      {/* composer */}
      <View style={{ display: 'flex', gap: '8px', padding: '10px', backgroundColor: '#fff', borderTop: '1px solid #e5e7eb' }}>
        <Textarea
          value={draft}
          onInput={(e) => setDraft(e.detail.value)}
          placeholder="问我任何数学问题…"
          autoHeight
          style={{ flex: 1, backgroundColor: '#f3f4f6', borderRadius: '10px', padding: '8px 10px', fontSize: '14px', maxHeight: '100px' }}
        />
        {canRegen && (
          <Button
            size="mini"
            style={{ backgroundColor: '#fff', color: '#4F46E5', border: '1px solid #4F46E5', borderRadius: '10px', fontSize: '13px' }}
            onClick={() => regenerate(stage)}
          >
            重答
          </Button>
        )}
        <Button
          loading={isRunning}
          disabled={isRunning}
          style={{ backgroundColor: '#4F46E5', color: '#fff', borderRadius: '10px', fontSize: '14px' }}
          onClick={onSend}
        >
          发送
        </Button>
      </View>
    </View>
  );
}
