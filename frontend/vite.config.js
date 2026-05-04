import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vitejs.dev/config/
// 部署在子路径时（如 http://IP/policy/）：构建前设置 VITE_APP_BASE=/policy/（须以 / 开头和结尾）
export default defineConfig({
  base: process.env.VITE_APP_BASE ?? '/',
  plugins: [vue()],
  // 未设置 VITE_API_BASE_URL 时，axios 会请求当前站点 /api/*；开发时由 Vite 转发到 Flask，避免 404。
  server: {
    proxy: {
      '/api': {
        target: process.env.VITE_DEV_API_PROXY ?? 'http://127.0.0.1:5005',
        changeOrigin: true,
      },
    },
  },
})
