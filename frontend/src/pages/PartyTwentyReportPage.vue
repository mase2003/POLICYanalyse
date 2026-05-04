<template>
  <section class="panel">
    <h3 class="page-title">{{ title }}</h3>
    <a-alert v-if="err" type="error" :message="err" show-icon class="mb" />
    <a-spin :spinning="loading">
      <div class="read-wrap">
        <div class="article">
          <p v-for="(p, i) in bundle?.paragraphs || []" :key="i" class="para">{{ p }}</p>
        </div>
        <aside class="side" >
          <div class="side-head">
            <span class="side-title">关键词</span>
           
          </div>
          <div class="side-body">
            <a-collapse v-model:activeKey="kwOpen">
              <a-collapse-panel key="four" header="四字词语（前25）">
                <a-table
                  :columns="cols"
                  :data-source="bundle?.analysis?.fourCharFrequency || []"
                  :pagination="false"
                  size="small"
                  row-key="word"
                />
              </a-collapse-panel>
              <a-collapse-panel key="noun" header="关键名词（前25）">
                <a-table
                  :columns="cols"
                  :data-source="bundle?.analysis?.nounFrequency || []"
                  :pagination="false"
                  size="small"
                  row-key="word"
                />
              </a-collapse-panel>
              <a-collapse-panel key="attr" header="定语统计（前25）">
                <a-table
                  :columns="cols"
                  :data-source="bundle?.analysis?.attributiveFrequency || []"
                  :pagination="false"
                  size="small"
                  row-key="word"
                />
              </a-collapse-panel>
              <a-collapse-panel key="gen" header="综合词频（25）">
                <a-table
                  :columns="cols"
                  :data-source="bundle?.analysis?.generalFrequency || []"
                  :pagination="false"
                  size="small"
                  row-key="word"
                />
              </a-collapse-panel>
            </a-collapse>
          </div>
        </aside>
      </div>
    </a-spin>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { fetchParty20Bundle } from '../api/policyForecast'

defineProps({
  title: { type: String, default: '二十大报告解析' },
})

const loading = ref(false)
const err = ref('')
const bundle = ref(null)
const sideCollapsed = ref(true)
const kwOpen = ref([])
const cols = [
  { title: '词语', dataIndex: 'word', key: 'word' },
  { title: '频次', dataIndex: 'count', key: 'count', width: 72 },
]

onMounted(async () => {
  loading.value = true
  err.value = ''
  try {
    bundle.value = await fetchParty20Bundle()
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
  background: rgb(239, 232, 230);
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px 14px;
  overflow: visible;
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
  transition: width 0.25s ease;
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
  }
  .side.collapsed {
    width: 100%;
  }
}
</style>
