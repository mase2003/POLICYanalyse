<template>
  <section class="panel">
    <h3 class="page-title">{{ title }}</h3>
    <a-alert v-if="err" type="error" :message="err" show-icon class="mb" />
    <a-spin :spinning="loading">
      <a-tabs v-model:activeKey="tab">
        <a-tab-pane key="main" tab="纲要原文">
          <div class="read-wrap">
            <div class="article">
              <p v-for="(p, i) in bundle?.main?.paragraphs || []" :key="'m' + i" class="para">{{ p }}</p>
            </div>
            <aside class="side" >
              <div class="side-head">
                <span class="side-title">关键词</span>
                
              </div>
              <div  class="side-body">
                <a-collapse v-model:activeKey="kwOpen">
                  <a-collapse-panel key="four" header="四字词语（前25）">
                    <a-table
                      :columns="cols"
                      :data-source="bundle?.mainAnalysis?.fourCharFrequency || []"
                      :pagination="false"
                      size="small"
                      row-key="word"
                    />
                  </a-collapse-panel>
                  <a-collapse-panel key="noun" header="关键名词（25）">
                    <a-table
                      :columns="cols"
                      :data-source="bundle?.mainAnalysis?.nounFrequency || []"
                      :pagination="false"
                      size="small"
                      row-key="word"
                    />
                  </a-collapse-panel>
                  <a-collapse-panel key="attr" header="定语统计（25）">
                    <a-table
                      :columns="cols"
                      :data-source="bundle?.mainAnalysis?.attributiveFrequency || []"
                      :pagination="false"
                      size="small"
                      row-key="word"
                    />
                  </a-collapse-panel>
                  <a-collapse-panel key="gen" header="综合词频（25）">
                    <a-table
                      :columns="cols"
                      :data-source="bundle?.mainAnalysis?.generalFrequency || []"
                      :pagination="false"
                      size="small"
                      row-key="word"
                    />
                  </a-collapse-panel>
                </a-collapse>
              </div>
            </aside>
          </div>
        </a-tab-pane>
        <a-tab-pane key="concept" tab="概念解读">
          <div class="article">
            <p  class="para">{{ conceptBody }}</p>
          </div>
        </a-tab-pane>
      </a-tabs>
    </a-spin>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { fetchFifteenFiveBundle } from '../api/policyForecast'

defineProps({
  title: { type: String, default: '十五五规划解析' },
})

const loading = ref(false)
const err = ref('')
const bundle = ref(null)
const tab = ref('main')
const sideCollapsed = ref(true)
const kwOpen = ref([])
const cols = [
  { title: '词语', dataIndex: 'word', key: 'word' },
  { title: '频次', dataIndex: 'count', key: 'count', width: 72 },
]

const conceptBody = computed(() => {
  const c = bundle.value?.concept
  if (!c) return ''
  if (c.fullText != null && String(c.fullText).length) return String(c.fullText)
  return (c.paragraphs || []).join('\n\n')
})

onMounted(async () => {
  loading.value = true
  err.value = ''
  try {
    bundle.value = await fetchFifteenFiveBundle()
  } catch (e) {
    err.value = e.response?.data?.error || e.message || '加载失败'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.panel {
  max-width: 1280px;
  margin: 0 auto;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 16px 20px;
}
.page-title {
  margin: 0 0 12px;
  font-size: 18px;
  color: #111827;
}
.mb {
  margin-bottom: 10px;
}
.read-wrap {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}
.article {
  flex: 1;
  min-width: 0;
  background:rgb(239, 232, 230);
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px 14px;
  overflow: visible;
}
.reader-panel {
  max-width: 980px;
  margin: 0 auto;
}
.reader-panel .meta {
  margin: 0 0 12px;
  color: #6b7280;
  font-size: 13px;
}
.reader-panel .content {
  white-space: pre-wrap;
  font-size: 13px;
  line-height: 1.6;
  background:rgb(212, 210, 215);
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px;
  overflow: visible;
  margin: 0;
  font-family: inherit;
}
.para {
  margin: 0 0 12px;
  white-space: pre-wrap;
  font-size: 13px;
  line-height: 1.65;
  color: #1f2937;
}
.para:last-child {
  margin-bottom: 0;
}
.side {
  width: 320px;
  flex-shrink: 0;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  display: flex;
  flex-direction: column;
  transition: width 0.25s ease, opacity 0.2s;
}
.side.collapsed {
  width: 88px;
  overflow: hidden;
}
.side-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 8px;
  border-bottom: 1px solid #f1f5f9;
}
.side-title {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
}
.side-body {
  overflow: visible;
  padding: 0;
  flex: 1;
}
@media (max-width: 960px) {
  .read-wrap {
    flex-direction: column;
  }
  .side {
    width: 100%;
    max-height: none;
  }
  .side.collapsed {
    width: 100%;
  }
}
</style>
