<template>
  <section class="panel">
    <h3 class="page-title">{{ title }}</h3>
    <div v-if="!graphFocusNodeId" class="empty-hint">请先在首页、政策目录或图谱中选择一条政策，再查看方向解析。</div>
    <template v-else>
      <div class="head">
        <div class="current">当前政策：{{ graphFocusTitle || '（无标题）' }}</div>
        <a-button :loading="loading" @click="reload">刷新解析</a-button>
      </div>
      <a-alert v-if="errorMsg" type="error" :message="errorMsg" show-icon class="err-alert" />
      <div v-if="analysis?.wordCloud?.length" class="word-cloud">
        <span
          v-for="item in analysis.wordCloud"
          :key="item.word"
          class="cloud-word"
          :style="{ fontSize: cloudFontSize(item.count) }"
        >
          {{ item.word }}
        </span>
      </div>
      <div v-if="analysis?.keywords?.length" class="keyword-list">
        <span v-for="item in analysis.keywords" :key="item.word" class="keyword-chip">{{ item.word }}</span>
      </div>
      <div class="analysis-grid">
        <div class="analysis-table">
          <h6>词频统计</h6>
          <a-table :columns="analysisColumns" :data-source="analysis?.wordFrequency || []" :pagination="false" size="small" row-key="word" />
        </div>
        <div class="analysis-table">
          <h6>定语统计</h6>
          <a-table :columns="analysisColumns" :data-source="analysis?.attributiveFrequency || []" :pagination="false" size="small" row-key="word" />
        </div>
        <div class="analysis-table">
          <h6>关键名词统计</h6>
          <a-table :columns="analysisColumns" :data-source="analysis?.nounFrequency || []" :pagination="false" size="small" row-key="word" />
        </div>
        <div class="analysis-table">
          <h6>四字词语统计</h6>
          <a-table :columns="analysisColumns" :data-source="analysis?.fourCharFrequency || []" :pagination="false" size="small" row-key="word" />
        </div>
      </div>
    </template>
  </section>
</template>

<script setup>
import { ref, watch } from 'vue'
import { fetchPolicyDirectionAnalysis } from '../api/graph'
import { graphFocusNodeId, graphFocusTitle } from '../composables/policyGraphContext'

defineProps({
  title: { type: String, default: '方向解析' },
})

const loading = ref(false)
const errorMsg = ref('')
const analysis = ref(null)
const analysisColumns = [
  { title: '词语', dataIndex: 'word', key: 'word' },
  { title: '频次', dataIndex: 'count', key: 'count', width: 80 },
]

async function reload() {
  if (!graphFocusNodeId.value) return
  loading.value = true
  errorMsg.value = ''
  try {
    analysis.value = await fetchPolicyDirectionAnalysis(graphFocusNodeId.value)
  } catch (e) {
    errorMsg.value = e.response?.data?.error || e.message || '方向解析失败'
    analysis.value = null
  } finally {
    loading.value = false
  }
}

function cloudFontSize(count) {
  const c = Number(count || 0)
  const clamped = Math.max(1, Math.min(c, 12))
  return `${14 + clamped * 3}px`
}

watch(
  () => graphFocusNodeId.value,
  () => {
    analysis.value = null
    if (graphFocusNodeId.value) reload()
  },
  { immediate: true },
)
</script>

<style scoped>
.panel {
  max-width: 1200px;
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
.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.current {
  font-size: 14px;
  color: #374151;
}
.empty-hint {
  font-size: 14px;
  color: #64748b;
  padding: 20px 12px;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  background: rgb(239, 232, 230);
}
.err-alert {
  margin-bottom: 10px;
}
.word-cloud {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  align-items: center;
  gap: 10px 14px;
  min-height: 120px;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  background: rgb(239, 232, 230);
  margin-bottom: 10px;
  padding: 10px;
}
.cloud-word {
  color: #334155;
  line-height: 1.1;
  font-weight: 600;
}
.keyword-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}
.keyword-chip {
  background: #F9EAD2;
  border: 1px solid #E6CBA8;
  color: #4B4453;
  border-radius: 999px;
  padding: 2px 10px;
  font-size: 12px;
}
.analysis-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(220px, 1fr));
  gap: 10px;
  overflow-x: auto;
  padding-bottom: 4px;
}
.analysis-table {
  min-width: 0;
}
.analysis-table h6 {
  margin: 0 0 6px;
  color: #334155;
  font-size: 13px;
}
@media (max-width: 1400px) {
  .analysis-grid {
    grid-template-columns: repeat(4, minmax(200px, 1fr));
  }
}
@media (max-width: 900px) {
  .analysis-grid {
    grid-template-columns: repeat(2, minmax(220px, 1fr));
  }
}
@media (max-width: 560px) {
  .analysis-grid {
    grid-template-columns: 1fr;
  }
}
</style>
