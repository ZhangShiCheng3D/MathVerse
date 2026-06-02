import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'cn.kuangyebar.mathverse',
  appName: '数界 MathVerse',
  webDir: 'dist',
  server: {
    androidScheme: 'https',
  },
  plugins: {
    // Route fetch/XHR (Taro.request in h5) through native HTTP so requests to
    // https://kuangyebar.cn are not subject to the WebView's CORS policy.
    CapacitorHttp: {
      enabled: true,
    },
  },
};

export default config;
