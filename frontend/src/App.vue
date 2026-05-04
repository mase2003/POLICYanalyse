<template>
  <div class="app-root">
    <header class="top-bar">
      <div class="top-bar-inner">
        <span class="top-brand">政策分析网站 </span>
        <div class="search-wrap">
          <a-input
            v-model:value="keyword"
            class="search-input"
            placeholder="搜索文件名称、发文机构…"
            allow-clear
            @pressEnter="submitSearch"
          />
          <a-button type="primary" @click="submitSearch">搜索</a-button>
          <a-button
            v-if="panelOpen"
            type="default"
            @click="closePanel"
          >
            关闭结果
          </a-button>
          <a-button type="link" class="home-btn" @click="goHome">首页</a-button>
        </div>
      </div>
    </header>

    <div class="app-body">
      <main class="app-router">
        <router-view />
      </main>
      <div v-if="panelOpen" class="result-modal-mask" aria-live="polite" @click.self="closePanel">
        <aside class="result-modal">
          <div class="result-head">
            <strong>搜索结果</strong>
            <span v-if="keyword" class="result-kw">「{{ keyword }}」</span>
          </div>
          <p v-if="loading" class="result-muted">加载中…</p>
          <p v-else-if="errorMsg" class="result-error">{{ errorMsg }}</p>
          <p v-else-if="!items.length" class="result-muted">未找到匹配项</p>
          <ul v-else class="result-list">
            <li v-for="it in items" :key="it.id" class="result-item">
              <a-button type="link" class="result-title btn-result" @click="openPolicy(it)">
                {{ it.fileName || '（无标题）' }}
              </a-button>
              <div v-if="it.organization" class="result-meta">发文机构：{{ it.organization }}</div>
            </li>
          </ul>
        </aside>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { searchPolicies } from './api/search'
import { focusPolicyForGraph, sidebarNavigateKey } from './composables/policyGraphContext'

const keyword = ref('')
const panelOpen = ref(false)
const loading = ref(false)
const errorMsg = ref('')
const items = ref([])
const router = useRouter()

async function submitSearch() {
  keyword.value = (keyword.value || '').trim()
  if (!keyword.value) {
    panelOpen.value = false
    items.value = []
    errorMsg.value = ''
    return
  }
  panelOpen.value = true
  loading.value = true
  errorMsg.value = ''
  try {
    const data = await searchPolicies(keyword.value)
    items.value = data.items || []
  } catch (e) {
    const msg =
      e.response?.data?.error ||
      (e.response?.data && typeof e.response.data === 'string' ? e.response.data : null) ||
      e.message ||
      '请求失败'
    errorMsg.value = msg
    items.value = []
  } finally {
    loading.value = false
  }
}

function closePanel() {
  panelOpen.value = false
}

function openPolicy(it) {
  if (!it?.id) return
  if (router.currentRoute.value.path !== '/neo4j') {
    router.push('/neo4j').catch(() => {})
  }
  focusPolicyForGraph(it.id, it.fileName || it.properties?.name || '')
  closePanel()
}

function goHome() {
  if (router.currentRoute.value.path !== '/neo4j') {
    router.push('/neo4j').catch(() => {})
  }
  sidebarNavigateKey.value = 'home'
}
</script>

<style scoped>
.app-root {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--page-bg);
}

.top-bar {
  flex-shrink: 0;
  background: var(--topbar-bg);
  border-bottom: 1px solid var(--control-border);
  box-shadow: 0 1px 2px rgba(45, 26, 23, 0.08);
  z-index: 20;
}

.top-bar-inner {
  max-width: 1600px;
  margin: 0 auto;
  padding: 10px 16px;
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.top-brand {
  font-weight: 700;
  color: var(--text-main);
  white-space: nowrap;
  font-family: Arial, "Microsoft YaHei", sans-serif;
}

.search-wrap {
  flex: 1;
  min-width: 200px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.home-btn {
  margin-left: auto;
}

.search-input {
  flex: 1;
  min-width: 160px;
  max-width: 560px;
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
}

.search-input:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.15);
}

.app-body {
  flex: 1;
  display: flex;
  min-height: 0;
}

.app-router {
  flex: 1;
  min-width: 0;
  min-height: 0;
  overflow: auto;
  display: flex;
  flex-direction: column;
}

.result-modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.35);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 72px;
  z-index: 50;
}

.result-modal {
  width: min(760px, calc(100vw - 32px));
  max-height: calc(100vh - 110px);
  background: var(--container-bg);
  border: 1px solid var(--container-border);
  border-radius: 10px;
  overflow: auto;
  padding: 16px 18px;
}

.result-head {
  margin-bottom: 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.result-kw {
  font-size: 12px;
  color: #64748b;
  word-break: break-all;
}

.result-muted {
  margin: 0;
  font-size: 13px;
  color: #64748b;
}

.result-error {
  margin: 0;
  font-size: 13px;
  color: #b91c1c;
}

.result-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.result-item {
  padding: 10px 0;
  border-bottom: 1px solid #f1f5f9;
}

.result-item:last-child {
  border-bottom: none;
}

.result-title {
  text-align: left !important;
  padding: 0 !important;
  font-size: 13px;
  line-height: 1.4;
  color: var(--text-main) !important;
}

.result-title:hover {
  color: var(--text-reactive);
  text-decoration: underline;
}

.result-meta {
  margin-top: 6px;
  font-size: 12px;
  color: #64748b;
}
</style>
