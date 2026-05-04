<template>
  <section class="panel">
    <div class="head">
      <h3>最新政策获取</h3>
    </div>

    <div class="grid">
      <label class="field">
        <span>爬取数量 *</span>
        <a-input-number v-model:value="form.limit" :min="1" :max="1000" style="width: 100%" />
      </label>
      <label class="field">
        <span>开始日期 *</span>
        <a-input v-model:value="form.startDate" type="date" />
      </label>
      <label class="field">
        <span>结束日期 *</span>
        <a-input v-model:value="form.endDate" type="date" />
      </label>
    </div>

    <div class="field">
      <span>爬取地区 *</span>
      <a-checkbox-group v-model:value="form.regions" :options="regionOptions" class="checks" />
    </div>

    <label class="field">
      <span>关键词</span>
      <a-input v-model:value="form.keywords" placeholder="多个关键词用空格或逗号分隔" />
    </label>

    <div v-if="errorMsg" class="msg error">{{ errorMsg }}</div>
    <div v-if="statusMsg" class="msg ok">{{ statusMsg }}</div>

    <div class="actions">
      <a-button type="primary" :loading="running" :disabled="running" @click="startFetch">
        {{ running ? '爬取中...' : '开始爬取' }}
      </a-button>
      <a-button :disabled="!selectedRowIds.length" @click="exportSelected">导出勾选 Excel</a-button>
      <a-button :disabled="!selectedRowIds.length || importing" :loading="importing" @click="importSelected">
        导入数据库
      </a-button>
    </div>

    <div v-if="taskState" class="task-box">
      <div>任务ID：{{ taskState.taskId }}</div>
      <div>状态：{{ taskState.status }}</div>
      <div>进度：{{ taskState.progress || 0 }}%</div>
      <div>匹配数据：{{ taskState.matched || 0 }}</div>
      <div>写入CSV：{{ taskState.written || 0 }}</div>
      <div>失败条数：{{ taskState.failed || 0 }}</div>
      <div>跳过条数：{{ taskState.skipped || 0 }}</div>
      <div v-if="taskState.reasonStats && Object.keys(taskState.reasonStats).length">
        跳过/失败原因：{{ formatReasonStats(taskState.reasonStats) }}
      </div>
    </div>

    <div v-if="taskItems.length" class="result-panel">
      <div class="result-head">
        <h4>本次爬取结果</h4>
        <span class="muted">CSV 会保留历史数据，重复内容用本次最新爬取结果覆盖。</span>
      </div>
      <a-table
        row-key="_rowId"
        :columns="columns"
        :data-source="taskItems"
        :pagination="{ pageSize: 10 }"
        :row-selection="{ selectedRowKeys: selectedRowIds, onChange: onSelectChange, preserveSelectedRowKeys: true }"
        size="middle"
      />
    </div>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { Modal } from 'ant-design-vue'
import {
  exportCrawlerXlsx,
  fetchCrawlerStatus,
  fetchLatestCrawlerTask,
  importCrawlerRows,
  startCrawlerTask,
} from '../api/crawler'

const regionOptions = ['北京市', '广东省', '四川省', '上海市']
const columns = [
  { title: '来源', dataIndex: '来源', key: '来源', customRender: ({ text }) => text || '—' },
  { title: '标题', dataIndex: '标题', key: '标题', customRender: ({ text }) => text || '—' },
  { title: '公文种类', dataIndex: '公文种类', key: '公文种类', customRender: ({ text }) => text || '—' },
  { title: '发文机构/发布机构', dataIndex: '发文机构\\发文机构', key: '发文机构\\发文机构', customRender: ({ text }) => text || '—' },
  { title: '发布日期', dataIndex: '发布日期', key: '发布日期', customRender: ({ text }) => text || '—' },
  { title: '联合发文单位', dataIndex: '联合发文单位', key: '联合发文单位', customRender: ({ text }) => text || '—' },
  { title: '发文字号/文号', dataIndex: '发文字号\\文号', key: '发文字号\\文号', customRender: ({ text }) => text || '—' },
  { title: '索引号', dataIndex: '索引号', key: '索引号', customRender: ({ text }) => text || '—' },
  { title: '主题分类/分类', dataIndex: '主题分类\\分类', key: '主题分类\\分类', customRender: ({ text }) => text || '—' },
  { title: '成文日期/印发日期', dataIndex: '成文日期\\印发日期', key: '成文日期\\印发日期', customRender: ({ text }) => text || '—' },
  { title: '实施日期', dataIndex: '实施日期', key: '实施日期', customRender: ({ text }) => text || '—' },
  { title: '废止日期', dataIndex: '废止日期', key: '废止日期', customRender: ({ text }) => text || '—' },
  { title: '有效性', dataIndex: '有效性', key: '有效性', customRender: ({ text }) => text || '—' },
]

const form = reactive({
  limit: null,
  startDate: '',
  endDate: '',
  regions: [],
  keywords: '',
})

const running = ref(false)
const importing = ref(false)
const errorMsg = ref('')
const statusMsg = ref('')
const taskId = ref('')
const taskState = ref(null)
const selectedRowIds = ref([])
const taskItems = computed(() => taskState.value?.items || [])
let statusTimer = null
/** 同一 task 完成后缓存提示只弹一次 */
let cacheModalShownForTaskId = ''

function validate() {
  if (!form.limit || !form.startDate || !form.endDate || form.regions.length === 0) return '请完善爬取参数'
  const limitNum = Number(form.limit)
  if (!Number.isInteger(limitNum) || limitNum <= 0) return '请输入有效正整数'
  if (limitNum > 1000) return '单次最大爬取数量需低于 1000'
  if (form.endDate < form.startDate) return '结束时间需晚于起始时间'
  return ''
}

async function startFetch() {
  errorMsg.value = ''
  statusMsg.value = ''
  selectedRowIds.value = []
  const err = validate()
  if (err) {
    errorMsg.value = err
    return
  }
  running.value = true
  cacheModalShownForTaskId = ''
  try {
    const data = await startCrawlerTask({
      limit: Number(form.limit),
      startDate: form.startDate,
      endDate: form.endDate,
      regions: form.regions,
      keywords: form.keywords,
    })
    taskId.value = data.taskId
    statusMsg.value = `任务已启动：${taskId.value}`
    pollStatus()
  } catch (e) {
    running.value = false
    errorMsg.value = e.response?.data?.error || e.message || '启动失败'
  }
}

function onSelectChange(keys) {
  selectedRowIds.value = keys
}

async function pollStatus() {
  if (statusTimer) window.clearInterval(statusTimer)
  statusTimer = window.setInterval(async () => {
    if (!taskId.value) return
    try {
      const st = await fetchCrawlerStatus(taskId.value)
      taskState.value = st
      statusMsg.value = st.message || ''
      if (st.status === 'done' || st.status === 'failed') {
        running.value = false
        window.clearInterval(statusTimer)
        statusTimer = null
        if (st.status === 'done' && taskId.value && cacheModalShownForTaskId !== taskId.value) {
          cacheModalShownForTaskId = taskId.value
          const sec = Number(st.cacheRetentionSec)
          const ttl = Number.isFinite(sec) && sec > 0 ? sec : 3600
          const human =
            ttl >= 3600
              ? `约 ${Math.max(1, Math.round(ttl / 3600))} 小时`
              : `约 ${Math.max(1, Math.round(ttl / 60))} 分钟`
          Modal.info({
            title: '采集完成',
            content: `本次任务数据将在服务器 Redis 缓存中保留 ${human}（默认 3600 秒）。「政策采集解析」依赖该缓存；过期后需重新采集。`,
          })
        }
      }
    } catch (e) {
      running.value = false
      window.clearInterval(statusTimer)
      statusTimer = null
      errorMsg.value = e.response?.data?.error || e.message || '状态获取失败'
    }
  }, 2000)
}

async function exportSelected() {
  errorMsg.value = ''
  try {
    const out = await exportCrawlerXlsx(taskId.value, selectedRowIds.value)
    statusMsg.value = `Excel 导出完成：${out.path}（${out.count} 条）`
  } catch (e) {
    errorMsg.value = e.response?.data?.error || e.message || 'Excel 导出失败'
  }
}

async function importSelected() {
  importing.value = true
  errorMsg.value = ''
  try {
    const out = await importCrawlerRows(taskId.value, selectedRowIds.value)
    statusMsg.value = `数据库导入完成：${out.imported} 条，首页与筛选数据已可直接刷新查看`
  } catch (e) {
    errorMsg.value = e.response?.data?.error || e.message || '导入失败'
  } finally {
    importing.value = false
  }
}

function formatReasonStats(stats) {
  const mapping = {
    date_out_of_range: '日期不在范围内',
    keyword_mismatch: '关键词不匹配',
    http_empty: '详情页请求失败',
    parse_error: '页面解析失败',
  }
  return Object.entries(stats)
    .map(([k, v]) => `${mapping[k] || k}:${v}`)
    .join('；')
}

onMounted(async () => {
  try {
    const st = await fetchLatestCrawlerTask()
    if (st?.taskId) {
      taskId.value = st.taskId
      taskState.value = st
    }
  } catch {
    /* 无历史任务或后端未就绪 */
  }
})

onBeforeUnmount(() => {
  if (statusTimer) {
    window.clearInterval(statusTimer)
    statusTimer = null
  }
})
</script>

<style scoped>
.panel {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 16px;
}
.head h3 {
  margin: 0;
}
.head p {
  margin: 8px 0 0;
  color: #64748b;
  font-size: 13px;
}
.grid {
  margin-top: 14px;
  display: grid;
  grid-template-columns: minmax(180px, 1fr) minmax(220px, 1fr) minmax(220px, 1fr);
  gap: 10px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 12px;
}
.field span {
  font-size: 13px;
  color: #334155;
}
.field :deep(.ant-input),
.field :deep(.ant-picker),
.field :deep(input[type='date']) {
  width: 100%;
}
.checks {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.actions {
  margin-top: 14px;
}
.msg {
  margin-top: 12px;
  font-size: 13px;
}
.msg.error {
  color: #b91c1c;
}
.msg.ok {
  color: #0f766e;
}
.task-box {
  margin-top: 12px;
  padding: 10px 12px;
  border: 1px dashed #cbd5e1;
  border-radius: 6px;
  background: rgb(239, 232, 230);
  font-size: 13px;
  line-height: 1.8;
}
.result-panel {
  margin-top: 18px;
}
.result-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.result-head h4 {
  margin: 0;
}
@media (max-width: 980px) {
  .grid {
    grid-template-columns: 1fr;
  }
  .result-head {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
