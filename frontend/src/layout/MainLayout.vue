<template>
  <div class="layout">
    <aside class="sidebar">
      <a-menu mode="inline" :selected-keys="[activeKey]" :items="menuItems" @click="onMenuClick" />
    </aside>
    <main class="content">
      <component
        :is="activePage.component"
        v-bind="activePage.props || {}"
        :title="activePage.title"
      />
    </main>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { menuRegistry } from '../router'
import { sidebarNavigateKey } from '../composables/policyGraphContext'

const activeKey = ref('home')

const activePage = computed(() => menuRegistry[activeKey.value] || menuRegistry.home)
const menuItems = [
  {
    key: 'groupCatalog',
    label: '政策目录',
    type: 'group',
    class: 'menu-group-catalog',
    children: [
      { key: 'catalogOrg', label: '发布机构筛选', class: 'menu-item-catalog-1' },
      { key: 'catalogTopic', label: '主题词筛选', class: 'menu-item-catalog-2' },
    ],
  },
  {
    key: 'groupRead',
    label: '政策解读',
    type: 'group',
    class: 'menu-group-read',
      children: [
      { key: 'graphPolicy', label: '单条政策文本知识图谱解析', class: 'menu-item-read-1' },
      { key: 'directionAnalysis', label: '方向解析', class: 'menu-item-read-2' },
      { key: 'policyDeconstruct', label: '政策拆解', class: 'menu-item-read-3' },
      { key: 'officialRead', label: '官方解读', class: 'menu-item-read-4' },
    ],
  },
  {
    key: 'groupForecast',
    label: '政策预测',
    type: 'group',
    class: 'menu-group-forecast',
    children: [
      { key: 'forecastFifteen', label: '十五五规划解析', class: 'menu-item-forecast-1' },
      { key: 'forecastParty20', label: '二十大报告解析', class: 'menu-item-forecast-2' },
      { key: 'forecastCrawler', label: '政策采集解析', class: 'menu-item-forecast-3' },
    ],
  },
  {
    key: 'groupFetch',
    label: '政策采集',
    type: 'group',
    class: 'menu-group-fetch',
    children: [
      { key: 'latestPolicyFetch', label: '最新政策获取', class: 'menu-item-fetch-1' },
      { key: 'policyContentManage', label: '政策内容管理', class: 'menu-item-fetch-2' },
    ],
  },
]

function onMenuClick({ key }) {
  if (menuRegistry[key]) activeKey.value = key
}

watch(
  sidebarNavigateKey,
  (k) => {
    if (k && menuRegistry[k]) {
      activeKey.value = k
      sidebarNavigateKey.value = null
    }
  },
  { flush: 'sync' },
)
</script>

<style scoped>
.layout {
  display: grid;
  grid-template-columns: 240px 1fr;
  flex: 1;
  min-height: 0;
}
.sidebar {
  border-right: 1px solid var(--control-border);
  background: var(--menu-bg);
  padding: 12px 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  overflow: auto;
}
.brand {
  margin: 0 0 16px;
  font-size: 16px;
  font-weight: 700;
  color: #111827;
  padding: 0 6px;
}
.content {
  padding: 16px;
  min-width: 0;
}

.sidebar :deep(.ant-menu) {
  background: transparent;
  color: var(--text-main);
  border-inline-end: none;
}

.sidebar :deep(.ant-menu-item-group-title) {
  color: var(--text-main);
  font-weight: 700;
}

.sidebar :deep(.ant-menu-item) {
  border-radius: 8px;
  margin-inline: 4px;
  color: var(--text-main);
}

.sidebar :deep(.ant-menu-item:hover) {
  color: var(--menu-hover-text) !important;
  background: var(--menu-hover-bg) !important;
}

.sidebar :deep(.ant-menu-item-selected) {
  color: #fff !important;
  background: var(--menu-selected-bg) !important;
}

.sidebar :deep(.menu-item-catalog-1) { background: #9d8e72; color: #fff; }
.sidebar :deep(.menu-item-catalog-2) { background: #b8ab8e; color: #fff; }
.sidebar :deep(.menu-item-read-1) { background: #b08863; color: #fff; }
.sidebar :deep(.menu-item-read-2) { background: #c9a585; color: #fff; }
.sidebar :deep(.menu-item-read-3) { background: #e3c4a8; color: var(--text-main); }
.sidebar :deep(.menu-item-read-4) { background: #edd7c4; color: var(--text-main); }
.sidebar :deep(.menu-item-forecast-1) { background: #d4b38b; color: var(--text-main); }
.sidebar :deep(.menu-item-forecast-2) { background: #e6cba8; color: var(--text-main); }
.sidebar :deep(.menu-item-forecast-3) { background: #f5e0c3; color: var(--text-main); }
.sidebar :deep(.menu-item-fetch-1) { background: #c89f94; color: #fff; }
.sidebar :deep(.menu-item-fetch-2) { background: #af8277; color: #fff; }
</style>
