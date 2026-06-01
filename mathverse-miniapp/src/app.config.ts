export default defineAppConfig({
  pages: [
    'pages/index/index',
    'pages/solve/index',
    'pages/learn/index',
    'pages/me/index',
  ],
  tabBar: {
    color: '#8b8fa6',
    selectedColor: '#4F46E5',
    backgroundColor: '#ffffff',
    // 图标资源缺失，先用纯文字 tabBar（微信允许）；补齐 assets/tab/*.png 后再加回 iconPath。
    list: [
      { pagePath: 'pages/index/index', text: '首页' },
      { pagePath: 'pages/solve/index', text: '解题' },
      { pagePath: 'pages/learn/index', text: '学习' },
      { pagePath: 'pages/me/index', text: '我的' },
    ],
  },
  window: {
    backgroundTextStyle: 'light',
    navigationBarBackgroundColor: '#4F46E5',
    navigationBarTitleText: '数界 MathVerse',
    navigationBarTextStyle: 'white',
  },
});
