import { defineConfig } from '@tarojs/cli';

export default defineConfig({
  projectName: 'mathverse-miniapp',
  date: '2026-06-01',
  designWidth: 750,
  deviceRatio: {
    640: 2.34 / 2,
    750: 1,
    375: 2,
    828: 1.81 / 2,
  },
  sourceRoot: 'src',
  outputRoot: 'dist',
  plugins: [
    '@tarojs/plugin-platform-weapp',
    '@tarojs/plugin-platform-h5',
  ],
  // Replace process.env.TARO_APP_API_URL at build time — the mini program runtime
  // has no `process`, so a surviving reference crashes app.js. Override per build
  // by setting TARO_APP_API_URL in the environment.
  defineConstants: {
    'process.env.TARO_APP_API_URL': JSON.stringify(
      process.env.TARO_APP_API_URL || 'https://kuangyebar.cn',
    ),
  },
  copy: {
    patterns: [],
    options: {},
  },
  framework: 'react',
  compiler: 'webpack5',
  mini: {
    postcss: {
      pxtransform: {
        enable: true,
        config: {},
      },
      cssModules: {
        enable: false,
        config: {},
      },
    },
  },
  h5: {
    publicPath: '/',
    staticDirectory: 'static',
    postcss: {
      autoprefixer: {
        enable: true,
        config: {},
      },
    },
  },
});
