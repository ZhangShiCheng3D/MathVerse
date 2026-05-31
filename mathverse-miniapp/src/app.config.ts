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
    list: [
      {
        pagePath: 'pages/index/index',
        text: '首页',
        iconPath: 'assets/tab/home.png',
        selectedIconPath: 'assets/tab/home-active.png',
      },
      {
        pagePath: 'pages/solve/index',
        text: '解题',
        iconPath: 'assets/tab/solve.png',
        selectedIconPath: 'assets/tab/solve-active.png',
      },
      {
        pagePath: 'pages/learn/index',
        text: '学习',
        iconPath: 'assets/tab/learn.png',
        selectedIconPath: 'assets/tab/learn-active.png',
      },
      {
        pagePath: 'pages/me/index',
        text: '我的',
        iconPath: 'assets/tab/me.png',
        selectedIconPath: 'assets/tab/me-active.png',
      },
    ],
  },
  window: {
    backgroundTextStyle: 'light',
    navigationBarBackgroundColor: '#4F46E5',
    navigationBarTitleText: '数界 MathVerse',
    navigationBarTextStyle: 'white',
  },
});
