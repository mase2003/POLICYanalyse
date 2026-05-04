<template>
  <section class="panel">
    <h3 class="page-title">{{ title }}</h3>
    <a-alert v-if="cacheStaleNotice" type="warning" :message="cacheStaleNotice" show-icon class="mb" />
    <a-alert v-if="err" type="error" :message="err" show-icon class="mb" />

    <div class="book-toolbar">
      <a-button :disabled="step === 0 || busy" @click="goPrev">上一步</a-button>
      <span class="step-label">第 {{ step + 1 }} / 5 步</span>
      <a-button v-if="step < 4" type="primary" :loading="busy && step === 0" :disabled="busy" @click="goNext">
        {{ step === 0 ? '按筛选分析并进入下一步' : '下一步' }}
      </a-button>
    </div>

    <div class="book-viewport">
      <div class="book-track" :style="{ transform: `translateX(-${step * 100}%)` }">
        <!-- 第1步：表格横向滚动 -->
        <div class="book-page">
          <p class="hint">基于当前最近一次采集任务数据；可按来源、公文种类、主题分类筛选，月份筛选为可选项。</p>
          <a-spin :spinning="taskLoading">
            <div v-if="!task" class="muted">暂无采集任务，请先在「最新政策获取」中执行采集。</div>
            <template v-else>
              <!-- 筛选栏横向滚动 -->
              <div class="filters-wrapper">
                <div class="filters">
                  <a-select
                    v-model:value="filterSource"
                    allow-clear
                    placeholder="来源（全部）"
                    class="f-item"
                    :options="optSources"
                  />
                  <a-select
                    v-model:value="filterDoc"
                    allow-clear
                    placeholder="公文种类（全部）"
                    class="f-item"
                    :options="optDocs"
                  />
                  <a-select
                    v-model:value="filterCat"
                    allow-clear
                    placeholder="主题分类（全部）"
                    class="f-item"
                    :options="optCats"
                  />
                  <a-date-picker
                    v-model:value="monthPicker"
                    picker="month"
                    value-format="YYYY-MM"
                    placeholder="统计月份"
                    class="f-item narrow"
                  />
                </div>
              </div>
              
              <div class="select-toolbar">
                <a-button size="small" @click="clearPreviewSelection">清空选择</a-button>
                <span class="muted">已选 {{ selectedPreviewRowIds.length }} 条</span>
                <p class="muted">
                  当前共 {{ previewRows.length }} 条。后续五步将基于所选数据分析，单击可查看全文、图谱、拆解。
                </p>
              </div>
              
              <!-- 第一步表格：横向滚动 -->
              <div class="table-x-scroll">
                <a-table
                  :columns="step1Cols"
                  :data-source="previewRows"
                  :pagination="{ pageSize: 8, size: 'small' }"
                  size="small"
                  row-key="_rowId"
                  :row-selection="previewRowSelection"
                  :custom-row="step1RowProps"
                />
              </div>
            </template>
          </a-spin>
        </div>

        <!-- 第2步：上下滚动 max 20行 -->
        <div class="book-page">
          <h4 class="sub">采集语料 · 关键词（约100）</h4>
          <div class="grid4">
            <div class="cell">
              <h6>四字词语（25）</h6>
              <div class="table-y-scroll-20">
                <a-table :columns="kwCols" :data-source="pipeline?.step2?.fourCharFrequency || []" size="small" row-key="word" :pagination="false" />
              </div>
            </div>
            <div class="cell">
              <h6>关键名词（25）</h6>
              <div class="table-y-scroll-20">
                <a-table :columns="kwCols" :data-source="pipeline?.step2?.nounFrequency || []" size="small" row-key="word" :pagination="false" />
              </div>
            </div>
            <div class="cell">
              <h6>定语统计（25）</h6>
              <div class="table-y-scroll-20">
                <a-table :columns="kwCols" :data-source="pipeline?.step2?.attributiveFrequency || []" size="small" row-key="word" :pagination="false" />
              </div>
            </div>
            <div class="cell">
              <h6>综合词频（25）</h6>
              <div class="table-y-scroll-20">
                <a-table :columns="kwCols" :data-source="pipeline?.step2?.generalFrequency || []" size="small" row-key="word" :pagination="false" />
              </div>
            </div>
          </div>
        </div>

        <!-- 第3步：上下滚动 max 20行 -->
        <div class="book-page">
          <h4 class="sub">与「十五五纲要 + 二十大报告」语料的重合关键词（各10）</h4>
          <div class="grid3">
            <div class="cell">
              
              <div class="table-y-scroll-20">
              <h6>四字重合</h6>
                <a-table :columns="kwCols" :data-source="pipeline?.step3?.overlapFour || []" size="small" row-key="word" :pagination="false" />
              </div>
            </div>
            <div class="cell">
              <h6>名词重合</h6>
              <div class="table-y-scroll-20">
                <a-table :columns="kwCols" :data-source="pipeline?.step3?.overlapNoun || []" size="small" row-key="word" :pagination="false" />
              </div>
            </div>
            <div class="cell">
              <h6>综合词频重合</h6>
              <div class="table-y-scroll-20">
                <a-table :columns="kwCols" :data-source="pipeline?.step3?.overlapGeneral || []" size="small" row-key="word" :pagination="false" />
              </div>
            </div>
          </div>
        </div>

        <!-- 第4步：上下滚动 max 20行 -->
        <div class="book-page">
          <h4 class="sub">相对纲要 / 报告的新词与在纲要中高频但采集语料中未出现的词</h4>
          <a-row :gutter="12">
            <a-col :xs="24" :md="12">
              <h6>新出现（节选）</h6>
              <div class="table-y-scroll-20">
                <a-table :columns="newCols" :data-source="pipeline?.step4?.newWords || []" size="small" row-key="word" :pagination="false" />
              </div>
            </a-col>
            <a-col :xs="24" :md="12">
              <h6>消失 / 减弱（节选）</h6>
              <div class="table-y-scroll-20">
                <a-table :columns="newCols" :data-source="pipeline?.step4?.disappeared || []" size="small" row-key="word" :pagination="false" />
              </div>
            </a-col>
          </a-row>
        </div>

        <!-- 第5步：上下滚动 max 20行 -->
        <div class="book-page">
          <h4 class="sub">趋势关键词与图库「文件名称」对比</h4>
          <p class="muted">
            下方候选词来自前几步汇总。请勾选关键词后点击按钮将给出结果。
            单击时可选择知识图谱、原文或政策拆解
          </p>
          <div v-if="(pipeline?.step5?.trendKeywords || []).length" class="trend-pick">
            <a-checkbox-group v-model:value="selectedTrendKeys" class="trend-checks">
              <a-checkbox v-for="w in pipeline?.step5?.trendKeywords || []" :key="w" :value="w">{{ w }}</a-checkbox>
            </a-checkbox-group>
            <div class="trend-actions">
              <a-button type="primary" :loading="busy" :disabled="!pipeline || !task?.taskId" @click="applyStep5Filter">
                关键词命中匹配
              </a-button>
              <a-button type="link" @click="selectAllTrend">全选</a-button>
              <a-button type="link" @click="clearTrend">清空</a-button>
            </div>
          </div>
          <p v-else class="muted">暂无候选趋势词，请返回第 1 步重新分析。</p>
          <div class="row-actions">
            <a-button type="primary" :loading="exporting" :disabled="!pipeline" @click="onExport">导出 Excel（五类工作表）</a-button>
          </div>
          <div class="select-toolbar">
            <span class="muted">第五步已选 {{ selectedStep5RowKeys.length }} 条</span>
            <a-button size="small" @click="clearStep5Selection">清空选择</a-button>
          </div>

          <!-- 第五步表格：上下滚动 -->
          <div class="table-y-scroll-20">
            <a-table
              :columns="step5Cols"
              :data-source="pagedPolicies"
              :pagination="{
                current: polPage,
                pageSize: polPageSize,
                total: policyTotal,
                showSizeChanger: true,
                pageSizeOptions: ['8', '16', '32'],
                showTotal: (t) => `共 ${t} 条`,
              }"
              size="small"
              row-key="_rowId"
              :custom-row="step5RowProps"
              :row-selection="step5RowSelection"
              @change="onPolTableChange"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === '文件名称'">
                  <a-tooltip :title="String(record['文件名称'] || '')" placement="topLeft">
                    <span class="title-cell fn-ellipsis">
                      <template v-for="(seg, i) in keywordSegments(record['文件名称'] || '', record)" :key="'fn' + i">
                        <span :class="{ hit: seg.hit }">{{ seg.text }}</span>
                      </template>
                    </span>
                  </a-tooltip>
                </template>
              </template>
            </a-table>
          </div>
        </div>
      </div>
    </div>

    <!-- 以下弹窗部分不变 -->
    <a-modal v-model:open="step1ChoiceOpen" title="请选择查看方式" :footer="null" width="400px">
      <div class="choice-actions choice-actions-triple">
        <a-button type="primary" block @click="openStep1Graph">知识图谱</a-button>
        <a-button block @click="openStep1Original">原文</a-button>
        <a-button block @click="openStep1Deconstruct">政策拆解</a-button>
      </div>
    </a-modal>

    <a-modal v-model:open="step5ChoiceOpen" title="请选择查看方式" :footer="null" width="400px">
      <div class="choice-actions choice-actions-triple">
        <a-button type="primary" block @click="openStep5Graph">知识图谱</a-button>
        <a-button block @click="openStep5Original">原文</a-button>
        <a-button block @click="openStep5Deconstruct">政策拆解</a-button>
      </div>
    </a-modal>

    <a-modal v-model:open="step1DetailOpen" title="" width="1100px" :footer="null">
      <div v-if="step1DetailLoading" class="loading-wrap">
        <a-spin />
        <span class="muted">原文加载中…</span>
      </div>
      <div v-else class="article-reader">
        <h2 class="article-title">{{ step1DetailTitle }}</h2>
        <div v-if="step1ArticleMeta.length" class="article-meta">
          <span v-for="field in step1ArticleMeta" :key="field.key">
            {{ field.label }}：{{ field.value }}
          </span>
        </div>
        <div class="article-content">
          <p v-for="(paragraph, idx) in step1ArticleParagraphs" :key="idx" class="article-paragraph">
            {{ paragraph }}
          </p>
        </div>
        <div v-if="step1ArticleExtra.length" class="article-extra-meta">
          <span v-for="field in step1ArticleExtra" :key="field.key">
            <template v-if="field.key === '网址' || field.key === '附件'">
              {{ field.label }}：
              <a :href="field.value" target="_blank" rel="noreferrer">{{ field.value }}</a>
            </template>
            <template v-else>{{ field.label }}：{{ field.value }}</template>
          </span>
        </div>
      </div>
    </a-modal>

    <a-modal v-model:open="step5DetailOpen" title="" width="1100px" :footer="null">
      <div v-if="step5DetailLoading" class="loading-wrap">
        <a-spin />
        <span class="muted">原文加载中…</span>
      </div>
      <div v-else class="article-reader">
        <h2 class="article-title">{{ step5DetailTitle }}</h2>
        <div v-if="step5ArticleMeta.length" class="article-meta">
          <span v-for="field in step5ArticleMeta" :key="field.key">
            {{ field.label }}：{{ field.value }}
          </span>
        </div>
        <div class="article-content">
          <p v-for="(paragraph, idx) in step5ArticleParagraphs" :key="idx" class="article-paragraph">
            {{ paragraph }}
          </p>
        </div>
        <div v-if="step5ArticleExtra.length" class="article-extra-meta">
          <span v-for="field in step5ArticleExtra" :key="field.key">
            <template v-if="field.key === '网址' || field.key === '附件'">
              {{ field.label }}：
              <a :href="field.value" target="_blank" rel="noreferrer">{{ field.value }}</a>
            </template>
            <template v-else>{{ field.label }}：{{ field.value }}</template>
          </span>
        </div>
      </div>
    </a-modal>
  </section>
</template>

<script setup>
// 脚本完全不变，直接复制你原来的即可
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { fetchLatestCrawlerTask } from '../api/crawler'
import { postCrawlerParse, postCrawlerParseExport } from '../api/policyForecast'
import { fetchPolicyDetail, resolvePolicyNode } from '../api/graph'
import { focusPolicyDeconstruct, focusPolicyForGraph } from '../composables/policyGraphContext'

defineProps({
  title: { type: String, default: '政策采集解析' },
})

const STEP1_KEYS = [
  '来源',
  '标题',
  '网址',
  '公文种类',
  '发文机构\\发文机构',
  '发布日期',
  '联合发文单位',
  '发文字号\\文号',
  '索引号',
  '有效性',
]

const taskLoading = ref(true)
const busy = ref(false)
const exporting = ref(false)
const err = ref('')
const cacheStaleNotice = ref('')
const task = ref(null)
const pipeline = ref(null)
const step = ref(0)

const filterSource = ref()
const filterDoc = ref()
const filterCat = ref()
const monthPicker = ref('')

const polPage = ref(1)
const polPageSize = ref(8)
const selectedTrendKeys = ref([])
const selectMode = ref('multiple')
const selectedPreviewRowIds = ref([])

const step5SelectMode = ref('multiple')
const selectedStep5RowKeys = ref([])

const step1ChoiceOpen = ref(false)
const step1DetailOpen = ref(false)
const step1DetailLoading = ref(false)
const step1PendingRow = ref(null)
const step1CurrentDetail = ref(null)

const step5ChoiceOpen = ref(false)
const step5PendingRow = ref(null)
const step5DetailOpen = ref(false)
const step5DetailLoading = ref(false)
const step5CurrentDetail = ref(null)

const STEP1_DETAIL_META = [
  { key: '发文机构\\发文机构', label: '发布机构' },
  { key: '公文种类', label: '公文种类' },
  { key: '联合发文单位', label: '联合发文单位' },
  { key: '索引号', label: '索引号' },
  { key: '主题分类\\分类', label: '主题分类/分类' },
  { key: '发布日期', label: '发布日期' },
  { key: '成文日期\\印发日期', label: '成文日期/印发日期' },
  { key: '实施日期', label: '实施日期' },
  { key: '废止日期', label: '废止日期' },
]
const STEP1_DETAIL_EXTRA = [
  { key: '网址', label: '网址' },
  { key: '来源', label: '来源' },
  { key: '有效性', label: '有效性' },
  { key: '附件', label: '附件' },
]

const kwCols = [
  { title: '词语', dataIndex: 'word', key: 'word' },
  { title: '频次', dataIndex: 'count', key: 'count', width: 72 },
]
const newCols = [
  { title: '词语', dataIndex: 'word', key: 'word' },
  { title: '频次', dataIndex: 'count', key: 'count', width: 72 },
]

const step1Cols = computed(() =>
  STEP1_KEYS.map((k) => ({
    title: k.replace(/\\/g, '/'),
    dataIndex: k,
    key: k,
    ellipsis: true,
    width: k === '标题' ? 220 : k === '网址' ? 160 : 120,
  })),
)

const step5Cols = computed(() => [
  { title: '文件名称', dataIndex: '文件名称', key: '文件名称', ellipsis: true, width: 320 },
  { title: '发文日期', dataIndex: '发文日期', key: '发文日期', width: 120 },
  { title: '主题分类', dataIndex: '主题分类', key: '主题分类', ellipsis: true, width: 140 },
  { title: '发文机构', dataIndex: '发文机构', key: '发文机构', ellipsis: true, width: 180 },
  { title: '命中关键词', dataIndex: 'matchedKeywords', key: 'mk', width: 200, ellipsis: true },
])

function stringHasExcludedChars(s) {
  if (!s || typeof s !== 'string') return false
  return /[\]\u201c\u201d\u2014"]/.test(s)
}

function sanitizeDisplayValue(v) {
  if (typeof v !== 'string') return v
  const s = v.trim()
  if (!s) return null
  const stripped = s.replace(/[\]\u201c\u201d\u2014"\s]/g, '')
  if (!stripped) return null
  return v
}

function publishInMonth(row, ym) {
  if (!ym) return true
  const blob = [row['发布日期'], row['成文日期\\印发日期']].filter(Boolean).join(' ')
  if (!blob.trim()) return false
  if (blob.includes(ym)) return true
  const [y, mo] = ym.split('-')
  if (!y || !mo) return true
  const mNum = String(Number(mo))
  return blob.includes(`${y}年${mNum}月`) || blob.includes(`${y}年${mo}月`)
}

function rowMatchesFilters(row) {
  if (filterSource.value && (row['来源'] || '').trim() !== filterSource.value) return false
  if (filterDoc.value && (row['公文种类'] || '').trim() !== filterDoc.value) return false
  if (filterCat.value && (row['主题分类\\分类'] || '').trim() !== filterCat.value) return false
  if (monthPicker.value && !publishInMonth(row, monthPicker.value)) return false
  return true
}

function mapStep1Row(row) {
  const o = { _rowId: row._rowId }
  for (const k of STEP1_KEYS) o[k] = sanitizeDisplayValue(row[k])
  return o
}

const previewRows = computed(() => {
  const items = task.value?.items || []
  return items.filter(rowMatchesFilters).map(mapStep1Row)
})

function rawItemByRowId(rowId) {
  const items = task.value?.items || []
  return items.find((r) => String(r._rowId) === String(rowId)) || null
}

function normalizeStep1DetailValue(value) {
  if (value == null) return ''
  const text = String(value).trim()
  if (!text) return ''
  if (/^[-—_\]\[()（）]+$/.test(text)) return ''
  return text
}

function step1ResolvedDetail(key) {
  const detail = step1CurrentDetail.value?.detail || {}
  const aliasKey = key.replace('发文机构', '发布机构')
  const candidateKeys = Array.from(
    new Set([key, aliasKey, ...key.split('\\'), ...aliasKey.split('\\')].filter(Boolean)),
  )
  for (const candidateKey of candidateKeys) {
    const value = normalizeStep1DetailValue(detail[candidateKey])
    if (value) return value
  }
  return ''
}

const step1DetailTitle = computed(() => step1ResolvedDetail('标题') || '—')

const step1ArticleMeta = computed(() =>
  STEP1_DETAIL_META.map((field) => ({
    ...field,
    value: step1ResolvedDetail(field.key),
  })).filter((field) => field.value),
)

const step1ArticleExtra = computed(() =>
  STEP1_DETAIL_EXTRA.map((field) => ({
    ...field,
    value: step1ResolvedDetail(field.key),
  })).filter((field) => field.value),
)

const step1ArticleParagraphs = computed(() => {
  const content = step1ResolvedDetail('正文')
  if (!content) return ['暂无正文内容']
  const paragraphs = content
    .split(/\r?\n+/)
    .map((x) => x.trim())
    .filter(Boolean)
  return paragraphs.length ? paragraphs : [content]
})

function step5ResolvedDetail(key) {
  const detail = step5CurrentDetail.value?.detail || {}
  const aliasKey = key.replace('发文机构', '发布机构')
  const candidateKeys = Array.from(
    new Set([key, aliasKey, ...key.split('\\'), ...aliasKey.split('\\')].filter(Boolean)),
  )
  for (const candidateKey of candidateKeys) {
    const value = normalizeStep1DetailValue(detail[candidateKey])
    if (value) return value
  }
  return ''
}

const step5DetailTitle = computed(() => step5ResolvedDetail('标题') || '—')

const step5ArticleMeta = computed(() =>
  STEP1_DETAIL_META.map((field) => ({
    ...field,
    value: step5ResolvedDetail(field.key),
  })).filter((field) => field.value),
)

const step5ArticleExtra = computed(() =>
  STEP1_DETAIL_EXTRA.map((field) => ({
    ...field,
    value: step5ResolvedDetail(field.key),
  })).filter((field) => field.value),
)

const step5ArticleParagraphs = computed(() => {
  const content = step5ResolvedDetail('正文')
  if (!content) return ['暂无正文内容']
  const paragraphs = content
    .split(/\r?\n+/)
    .map((x) => x.trim())
    .filter(Boolean)
  return paragraphs.length ? paragraphs : [content]
})

function buildCrawlerDetailMap(raw) {
  const d = {}
  if (!raw) return d
  const keys = [
    '标题',
    '正文',
    '来源',
    '公文种类',
    '网址',
    '发布日期',
    '成文日期\\印发日期',
    '发文机构\\发文机构',
    '联合发文单位',
    '发文字号\\文号',
    '索引号',
    '主题分类\\分类',
    '实施日期',
    '废止日期',
    '有效性',
    '附件',
  ]
  for (const k of keys) {
    const v = raw[k]
    if (v != null && String(v).trim()) d[k] = v
  }
  return d
}

function step1RowProps(record) {
  return {
    style: 'cursor: default',
    onClick: (e) => {
      if (e.target.closest?.('.ant-checkbox-wrapper') || e.target.closest?.('.ant-checkbox')) return
      step1PendingRow.value = record
      step1ChoiceOpen.value = true
    },
  }
}

async function openStep1Graph() {
  const preview = step1PendingRow.value
  step1ChoiceOpen.value = false
  if (!preview?._rowId) return
  const raw = rawItemByRowId(preview._rowId)
  const title = (preview['标题'] || raw?.['标题'] || '').trim()
  const url = (preview['网址'] || raw?.['网址'] || '').trim()
  try {
    const { nodeId } = await resolvePolicyNode({ title, url })
    if (nodeId) focusPolicyForGraph(nodeId, title)
    else message.warning('图库中未找到该条政策，可先「导入数据库」后再试')
  } catch (e) {
    message.error(e.response?.data?.error || e.message || '解析节点失败')
  }
}

async function openStep1Deconstruct() {
  const preview = step1PendingRow.value
  step1ChoiceOpen.value = false
  if (!preview?._rowId) return
  const raw = rawItemByRowId(preview._rowId)
  const title = (preview['标题'] || raw?.['标题'] || '').trim()
  const url = (preview['网址'] || raw?.['网址'] || '').trim()
  try {
    const { nodeId } = await resolvePolicyNode({ title, url })
    if (nodeId) focusPolicyDeconstruct(nodeId, title)
    else message.warning('图库中未找到该条政策，可先「导入数据库」后再试')
  } catch (e) {
    message.error(e.response?.data?.error || e.message || '解析节点失败')
  }
}

async function openStep1Original() {
  const preview = step1PendingRow.value
  step1ChoiceOpen.value = false
  if (!preview?._rowId) return
  const raw = rawItemByRowId(preview._rowId)
  const title = (preview['标题'] || raw?.['标题'] || '').trim()
  const url = (preview['网址'] || raw?.['网址'] || '').trim()
  step1DetailOpen.value = true
  step1DetailLoading.value = true
  step1CurrentDetail.value = null
  try {
    const { nodeId } = await resolvePolicyNode({ title, url })
    if (nodeId) {
      step1CurrentDetail.value = await fetchPolicyDetail(nodeId)
    } else {
      step1CurrentDetail.value = { detail: buildCrawlerDetailMap(raw || preview) }
    }
  } catch (e) {
    step1DetailOpen.value = false
    message.error(e.response?.data?.error || e.message || '原文加载失败')
  } finally {
    step1DetailLoading.value = false
  }
}

function step5RowProps(record) {
  return {
    style: 'cursor: pointer',
    onClick: (e) => {
      if (
        e.target.closest?.('.ant-pagination') ||
        e.target.closest?.('.ant-select-selector') ||
        e.target.closest?.('.ant-pagination-options') ||
        e.target.closest?.('.ant-table-selection-column') ||
        e.target.closest?.('.ant-checkbox-wrapper') ||
        e.target.closest?.('.ant-radio-wrapper') ||
        e.target.closest?.('.ant-checkbox') ||
        e.target.closest?.('.ant-radio')
      ) {
        return
      }
      step5PendingRow.value = record
      step5ChoiceOpen.value = true
    },
  }
}

function openStep5Graph() {
  const row = step5PendingRow.value
  step5ChoiceOpen.value = false
  if (!row?.neo4jId) {
    message.warning('缺少图库节点，无法打开知识图谱')
    return
  }
  focusPolicyForGraph(row.neo4jId, row['文件名称'] || '')
}

async function openStep5Original() {
  const row = step5PendingRow.value
  step5ChoiceOpen.value = false
  if (!row?.neo4jId) {
    message.warning('缺少图库节点，无法加载原文')
    return
  }
  step5DetailOpen.value = true
  step5DetailLoading.value = true
  step5CurrentDetail.value = null
  try {
    step5CurrentDetail.value = await fetchPolicyDetail(row.neo4jId)
  } catch (e) {
    step5DetailOpen.value = false
    message.error(e.response?.data?.error || e.message || '原文加载失败')
  } finally {
    step5DetailLoading.value = false
  }
}

function openStep5Deconstruct() {
  const row = step5PendingRow.value
  step5ChoiceOpen.value = false
  if (!row?.neo4jId) {
    message.warning('缺少图库节点')
    return
  }
  focusPolicyDeconstruct(row.neo4jId, row['文件名称'] || '')
}

const previewRowSelection = computed(() => ({
  type: selectMode.value === 'single' ? 'radio' : 'checkbox',
  preserveSelectedRowKeys: true,
  selectedRowKeys: selectedPreviewRowIds.value,
  onChange: (keys) => {
    if (selectMode.value === 'single') {
      selectedPreviewRowIds.value = keys.length ? [keys[keys.length - 1]] : []
      return
    }
    selectedPreviewRowIds.value = [...keys]
  },
}))

const step5RowSelection = computed(() => ({
  type: step5SelectMode.value === 'single' ? 'radio' : 'checkbox',
  preserveSelectedRowKeys: true,
  selectedRowKeys: selectedStep5RowKeys.value,
  onChange: (keys) => {
    if (step5SelectMode.value === 'single') {
      selectedStep5RowKeys.value = keys.length ? [keys[keys.length - 1]] : []
      return
    }
    selectedStep5RowKeys.value = [...keys]
  },
}))

function clearStep5Selection() {
  selectedStep5RowKeys.value = []
}

function clearParsePipelineState() {
  pipeline.value = null
  selectedPreviewRowIds.value = []
  selectedTrendKeys.value = []
  selectedStep5RowKeys.value = []
  polPage.value = 1
  step.value = 0
}

function uniqVals(key) {
  const items = task.value?.items || []
  const s = new Set()
  for (const r of items) {
    const v = (r[key] || '').trim()
    if (v) s.add(v)
  }
  return [...s].sort().map((v) => ({ label: v, value: v }))
}

const optSources = computed(() => uniqVals('来源'))
const optDocs = computed(() => uniqVals('公文种类'))
const optCats = computed(() => uniqVals('主题分类\\分类'))

const policies = computed(() => pipeline.value?.step5?.policies || [])
const policyTotal = computed(() => policies.value.length)

const pagedPolicies = computed(() => {
  const list = policies.value.map((r) => {
    const o = { ...r }
    o.matchedKeywords = (r.matchedKeywords || []).join('、')
    return o
  })
  const start = (polPage.value - 1) * polPageSize.value
  return list.slice(start, start + polPageSize.value)
})

function onPolTableChange(pag) {
  if (pag?.current != null) polPage.value = pag.current
  if (pag?.pageSize != null) polPageSize.value = pag.pageSize
}

watch(step, (s) => {
  if (s === 4) polPage.value = 1
})

watch(selectMode, (mode) => {
  if (mode === 'single' && selectedPreviewRowIds.value.length > 1) {
    selectedPreviewRowIds.value = selectedPreviewRowIds.value.slice(0, 1)
  }
})

watch(previewRows, (rows) => {
  const valid = new Set(rows.map((r) => r._rowId))
  selectedPreviewRowIds.value = selectedPreviewRowIds.value.filter((id) => valid.has(id))
})

watch(policies, (list) => {
  const valid = new Set(list.map((r) => r._rowId))
  selectedStep5RowKeys.value = selectedStep5RowKeys.value.filter((id) => valid.has(id))
})

watch(step5SelectMode, (mode) => {
  if (mode === 'single' && selectedStep5RowKeys.value.length > 1) {
    selectedStep5RowKeys.value = selectedStep5RowKeys.value.slice(0, 1)
  }
})

function keywordSegments(text, record) {
  const kws = record.matchedKeywords
    ? String(record.matchedKeywords)
        .split('、')
        .filter(Boolean)
    : []
  const hits = [...new Set(kws.filter((k) => k && text.includes(k)))].sort((a, b) => b.length - a.length)
  if (!text || !hits.length) return [{ text: text || '—', hit: false }]
  let i = 0
  const raw = []
  while (i < text.length) {
    let hit = null
    for (const k of hits) {
      if (text.slice(i, i + k.length) === k) {
        hit = k
        break
      }
    }
    if (hit) {
      raw.push({ text: hit, hit: true })
      i += hit.length
    } else {
      raw.push({ text: text[i], hit: false })
      i += 1
    }
  }
  const merged = []
  for (const p of raw) {
    const last = merged[merged.length - 1]
    if (last && last.hit === p.hit) last.text += p.text
    else merged.push({ ...p })
  }
  return merged
}

function onDocumentVisibleRefresh() {
  if (document.visibilityState === 'visible') loadTask()
}

async function loadTask() {
  taskLoading.value = true
  err.value = ''
  cacheStaleNotice.value = ''
  try {
    const data = await fetchLatestCrawlerTask()
    if (data?.fromCsvFallback) {
      clearParsePipelineState()
      task.value = null
      cacheStaleNotice.value =
        '采集任务在 Redis 中的缓存已过期，解析列表已清空。请到「最新政策获取」重新执行采集；完成后返回本页或切换到本标签页即可加载新任务（缓存约保留 1 小时，以服务器 CRAWLER_CACHE_TTL_SEC 为准）。'
      return
    }
    task.value = data
  } catch (e) {
    if (e.response?.status === 404) {
      task.value = null
    } else {
      err.value = e.response?.data?.error || e.message || '加载采集任务失败'
      task.value = null
    }
  } finally {
    taskLoading.value = false
  }
}

function parseBody() {
  const body = {
    taskId: task.value?.taskId,
    source: filterSource.value || '',
    docType: filterDoc.value || '',
    category: filterCat.value || '',
    month: monthPicker.value || '',
  }
  if (selectedPreviewRowIds.value?.length) {
    body.selectedRowIds = [...selectedPreviewRowIds.value]
  }
  if (selectedTrendKeys.value?.length) {
    body.selectedTrendKeywords = [...selectedTrendKeys.value]
  }
  return body
}

function clearPreviewSelection() {
  selectedPreviewRowIds.value = []
}

function selectAllTrend() {
  const list = pipeline.value?.step5?.trendKeywords || []
  selectedTrendKeys.value = [...list]
}

function clearTrend() {
  selectedTrendKeys.value = []
}

async function applyStep5Filter() {
  if (!task.value?.taskId) {
    message.warning('暂无采集任务')
    return
  }
  if (!selectedTrendKeys.value?.length) {
    message.warning('请至少勾选一个趋势关键词')
    return
  }
  await runPipeline()
  polPage.value = 1
}

async function runPipeline() {
  busy.value = true
  err.value = ''
  try {
    pipeline.value = await postCrawlerParse(parseBody())
    const sel = pipeline.value?.filters?.selectedTrendKeywords
    if (Array.isArray(sel) && sel.length) {
      selectedTrendKeys.value = [...sel]
    }
  } catch (e) {
    err.value = e.response?.data?.error || e.message || '分析失败'
    throw e
  } finally {
    busy.value = false
  }
}

async function goNext() {
  if (step.value === 0) {
    if (!task.value?.taskId) {
      message.warning('暂无采集任务')
      return
    }
    if (!selectedPreviewRowIds.value.length) {
      message.info('未勾选具体数据，将基于当前筛选结果中的全部数据分析')
    }
    selectedTrendKeys.value = []
    await runPipeline()
    step.value = 1
    return
  }
  if (step.value < 4) step.value += 1
}

function goPrev() {
  if (step.value > 0) step.value -= 1
}

async function onExport() {
  if (!task.value?.taskId) {
    message.warning('暂无任务可导出')
    return
  }
  exporting.value = true
  try {
    const res = await postCrawlerParseExport(parseBody())
    const blob = new Blob([res.data], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })
    let name = `policy_parse_${Date.now()}.xlsx`
    const dispo = res.headers['content-disposition']
    if (dispo) {
      const m = /filename\*=UTF-8''([^;]+)|filename="([^"]+)"/i.exec(dispo)
      const raw = decodeURIComponent(m?.[1] || m?.[2] || '')
      if (raw) name = raw
    }
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = name
    a.click()
    URL.revokeObjectURL(url)
    message.success('已开始下载')
  } catch (e) {
    const data = e.response?.data
    if (data instanceof Blob) {
      try {
        const t = await data.text()
        const j = JSON.parse(t)
        message.error(j.error || '导出失败')
      } catch {
        message.error('导出失败')
      }
    } else {
      message.error(e.response?.data?.error || e.message || '导出失败')
    }
  } finally {
    exporting.value = false
  }
}

onMounted(async () => {
  monthPicker.value = ''
  document.addEventListener('visibilitychange', onDocumentVisibleRefresh)
  await loadTask()
})

onUnmounted(() => {
  document.removeEventListener('visibilitychange', onDocumentVisibleRefresh)
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
  margin: 0 0 10px;
  font-size: 18px;
  color: #111827;
}
.mb {
  margin-bottom: 10px;
}
.book-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.step-label {
  font-size: 14px;
  color: #475569;
  font-weight: 600;
}
.book-viewport {
  overflow: hidden;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: #fafafa;
}
.book-track {
  display: flex;
  width: 100%;
  transition: transform 0.45s ease;
}
.book-page {
  flex: 0 0 100%;
  width: 100%;
  box-sizing: border-box;
  padding: 14px 16px 20px;
  background: #f7f6f1;
}
.hint {
  font-size: 13px;
  color: #64748b;
  margin: 0 0 10px;
}
.muted {
  font-size: 13px;
  color: #6b7280;
  margin: 6px 0 10px;
}

/* 筛选栏横向滚动 */
.filters-wrapper {
  width: 100%;
  overflow-x: auto;
  overflow-y: hidden;
  padding-bottom: 6px;
}
.filters {
  display: flex;
  gap: 8px;
  flex-wrap: nowrap;
  min-width: max-content;
}

.select-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.f-item {
  min-width: 200px;
  flex: 1;
}
.f-item.narrow {
  min-width: 160px;
  flex: 0;
}
.sub {
  margin: 0 0 10px;
  font-size: 15px;
  color: #1e293b;
}
.grid4 {
  display: grid;
  grid-template-columns: repeat(4, minmax(200px, 1fr));
  gap: 10px;
}
.grid3 {
  display: grid;
  grid-template-columns: repeat(3, minmax(200px, 1fr));
  gap: 10px;
}
.cell {
  min-width: 0;
}
.cell h6,
h6 {
  margin: 0 0 6px;
  font-size: 13px;
  color: #334155;
}

/* 第一步表格：横向滚动 */
.table-x-scroll {
  width: 100%;
  overflow-x: auto;
}

/* 第2-5步表格：纵向滚动 最多20行 */
.table-y-scroll-20 {
  max-height: 420px; /* 约20行高度 */
  overflow-y: auto;
  overflow-x: hidden;
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}
.chip {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 999px;
  background: #F9EAD2;
  border: 1px solid #E6CBA8;
  color: #4B4453;
}
.row-actions {
  margin-bottom: 10px;
}
.title-cell {
  cursor: default;
  color: inherit;
}
.link-like {
  cursor: pointer;
  color: #2563eb;
  text-decoration: underline;
}
.hit {
  color: #dc2626;
  font-weight: 700;
}
.trend-pick {
  margin-bottom: 12px;
  padding: 10px 12px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}
.trend-checks {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  margin-bottom: 8px;
}
.trend-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
@media (max-width: 1100px) {
  .grid4 {
    grid-template-columns: repeat(2, minmax(180px, 1fr));
  }
}
.loading-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 24px 0;
}
.choice-actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.choice-actions-triple {
  gap: 10px;
}
.fn-ellipsis {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: bottom;
}
.article-reader {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.article-title {
  margin: 0;
  font-size: 28px;
  line-height: 1.45;
  color: #111827;
}
.article-meta {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
  color: #6b7280;
  font-size: 14px;
}
.article-content {
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: rgb(239, 232, 230);
  font-size: 13px;
  line-height: 1.6;
  color: #0f172a;
}
.article-paragraph {
  margin: 0 0 8px;
  white-space: pre-wrap;
  word-break: break-word;
  text-indent: 2em;
}
.article-paragraph:last-child {
  margin-bottom: 0;
}
.article-extra-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 20px;
  color: #94a3b8;
  font-size: 12px;
  line-height: 1.7;
}
</style>