import { useState } from 'react';
import { View, Text, Input, Button } from '@tarojs/components';
import Taro from '@tarojs/taro';
import { useUserStore } from '../../stores/user';

const STAGES = [
  { id: 'primary-low', label: '小学低段' },
  { id: 'primary-high', label: '小学高段' },
  { id: 'junior', label: '初中' },
  { id: 'senior', label: '高中' },
  { id: 'college', label: '大学' },
  { id: 'kaoyan', label: '考研' },
];

const EXAM_MODES = [
  { id: 'math-1', label: '数学一' },
  { id: 'math-2', label: '数学二' },
  { id: 'math-3', label: '数学三' },
];

const Chips = ({ options, value, onPick }: {
  options: { id: string; label: string }[]; value: string; onPick: (id: string) => void;
}) => (
  <View style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
    {options.map((o) => {
      const on = value === o.id;
      return (
        <Text
          key={o.id}
          onClick={() => onPick(o.id)}
          style={{
            padding: '8px 18px', borderRadius: '9999px', fontSize: '14px',
            backgroundColor: on ? '#4F46E5' : '#fff',
            color: on ? '#fff' : '#374151',
            border: on ? 'none' : '1px solid #e5e7eb',
          }}
        >
          {o.label}
        </Text>
      );
    })}
  </View>
);

export default function SettingsPage() {
  const user = useUserStore((s) => s.user);
  const updateProfile = useUserStore((s) => s.updateProfile);
  const [stage, setStage] = useState(
    user?.current_stage && user.current_stage !== 'unset' ? user.current_stage : 'college'
  );
  const [exam, setExam] = useState(user?.exam_mode || '');
  const [nickname, setNickname] = useState(user?.nickname || '');
  const [saving, setSaving] = useState(false);

  const showExam = stage === 'kaoyan' || stage === 'college';

  if (!user) {
    return (
      <View style={{ padding: '48px', textAlign: 'center' }}>
        <Text style={{ color: '#9ca3af' }}>请先登录</Text>
      </View>
    );
  }

  const save = async () => {
    setSaving(true);
    try {
      await updateProfile({
        current_stage: stage,
        exam_mode: showExam ? exam : '',
        nickname,
      });
      Taro.showToast({ title: '已保存', icon: 'success' });
      setTimeout(() => { Taro.navigateBack().catch(() => {}); }, 500);
    } catch (e: any) {
      Taro.showToast({ title: e?.message || '保存失败', icon: 'none' });
    }
    setSaving(false);
  };

  return (
    <View style={{ minHeight: '100vh', backgroundColor: '#f3f4f6', padding: '16px' }}>
      <View style={{ backgroundColor: '#fff', borderRadius: '12px', padding: '16px', marginBottom: '14px' }}>
        <Text style={{ display: 'block', fontSize: '13px', color: '#6b7280', marginBottom: '10px' }}>昵称</Text>
        <Input
          value={nickname}
          maxlength={20}
          placeholder='输入昵称'
          onInput={(e) => setNickname(e.detail.value)}
          style={{ border: '1px solid #e5e7eb', borderRadius: '10px', padding: '10px 12px', fontSize: '15px' }}
        />
      </View>

      <View style={{ backgroundColor: '#fff', borderRadius: '12px', padding: '16px', marginBottom: '14px' }}>
        <Text style={{ display: 'block', fontSize: '13px', color: '#6b7280', marginBottom: '12px' }}>当前学段</Text>
        <Chips options={STAGES} value={stage} onPick={setStage} />
        <Text style={{ display: 'block', fontSize: '11.5px', color: '#9ca3af', marginTop: '10px' }}>
          学段决定知识地图、估分、计划与讲解内容
        </Text>
      </View>

      {showExam && (
        <View style={{ backgroundColor: '#fff', borderRadius: '12px', padding: '16px', marginBottom: '14px' }}>
          <Text style={{ display: 'block', fontSize: '13px', color: '#6b7280', marginBottom: '12px' }}>考研数学类型</Text>
          <Chips options={EXAM_MODES} value={exam} onPick={(id) => setExam(exam === id ? '' : id)} />
          <Text style={{ display: 'block', fontSize: '11.5px', color: '#9ca3af', marginTop: '10px' }}>
            用于估分预测（再次点击可取消）
          </Text>
        </View>
      )}

      <Button
        style={{ backgroundColor: '#4F46E5', color: '#fff', borderRadius: '9999px', fontSize: '16px', fontWeight: '600', marginTop: '6px' }}
        loading={saving}
        disabled={saving}
        onClick={save}
      >
        保存
      </Button>

      <View
        style={{ backgroundColor: '#fff', borderRadius: '12px', padding: '14px 16px', marginTop: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
        onClick={() => Taro.navigateTo({ url: '/pages/memory/index' })}
      >
        <Text style={{ fontSize: '14px', color: '#374151' }}>引擎记忆（只读·共享）</Text>
        <Text style={{ fontSize: '14px', color: '#9ca3af' }}>›</Text>
      </View>
    </View>
  );
}
