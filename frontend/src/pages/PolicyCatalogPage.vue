<template>
  <section class="catalog">
    <h3 class="page-title">{{ title }}</h3>
    <a-alert v-if="loadError" type="error" :message="loadError" show-icon />
    <div v-else-if="filtersLoading" class="loading-wrap">
      <a-spin />
      <span class="muted">筛选条件加载中…</span>
    </div>

    <template v-else>
      <!-- 发布机构筛选：仅按发文机构 -->
      <div v-if="isOrgMode" class="toolbar">
        <div class="toolbar-grid">
          <label class="field">
            <span class="label">发文机构</span>
            <a-select
              v-model:value="selectedOrg"
              class="select"
              placeholder="全部机构"
              allow-clear
              show-search
              :options="organizations.map((o) => ({ label: o, value: o }))"
              @change="onFilterChange"
            />
          </label>
          <label class="field">
            <span class="label">地区</span>
            <a-select
              v-model:value="selectedRegion"
              class="select"
              placeholder="全部地区"
              allow-clear
              show-search
              :options="regions.map((r) => ({ label: r, value: r }))"
              @change="onFilterChange"
            />
          </label>
        </div>
      </div>

      <!-- 主题词筛选：仅按主题词（与库中政策类型/主题词字段一致） -->
      <div v-else class="topics-block">
        <div class="topics-head">
          <span class="label">主题词</span>
          
        </div>
        <div class="chips" role="list">
          <a-button
            v-for="(t, i) in topics"
            :key="t"
            role="listitem"
            class="chip"
            :class="[topicChipClass(i), { active: selectedTopic === t }]"
            @click="selectTopic(t)"
          >
            {{ t }}
          </a-button>
        </div>
        <div v-if="selectedTopic && topicChildren.length" class="topic-children">
          <span class="label">主题分类</span>
          <div class="chips" role="list">
            <a-button
              v-for="(c, i) in topicChildren"
              :key="c.name"
              class="chip chip-sub"
              :class="[childChipClass(i), { active: selectedTopicChild === c.name }]"
              @click="selectTopicChild(c.name)"
            >
              {{ c.name }}
            </a-button>
          </div>
        </div>
      </div>

      <a-alert v-if="tableError" type="error" :message="tableError" show-icon />
      <div v-else-if="tableLoading" class="loading-wrap">
        <a-spin />
        <span class="muted">政策列表加载中…</span>
      </div>

      <div v-else class="table-wrap">
        <a-table
          :columns="antColumns"
          :data-source="items"
          :pagination="false"
          size="middle"
          row-key="id"
          :custom-row="tableRowProps"
        />
        <p v-if="!items.length" class="muted empty">暂无匹配政策，可调整筛选条件。</p>

        <div v-if="total > 0" class="pager">
          <span class="muted">共 {{ total }} 条</span>
          <a-pagination
            :current="page"
            :total="total"
            :page-size="pageSize"
            :show-size-changer="false"
            @change="goPage"
          />
        </div>
      </div>
    </template>

    <a-modal v-model:open="choiceModalOpen" title="请选择查看方式" :footer="null" width="400px">
      <div class="choice-actions choice-actions-triple">
        <a-button type="primary" block @click="openGraphView">知识图谱</a-button>
        <a-button block @click="openOriginalView">原文</a-button>
        <a-button block @click="openDeconstructView">政策拆解</a-button>
      </div>
    </a-modal>

    <a-modal v-model:open="detailModalOpen" title="" width="1100px" :footer="null">
      <div v-if="detailLoading" class="loading-wrap">
        <a-spin />
        <span class="muted">原文加载中…</span>
      </div>
      <div v-else class="article-reader">
        <h2 class="article-title">{{ detailValue('标题') }}</h2>
        <div v-if="articleMetaFields.length" class="article-meta">
          <span v-for="field in articleMetaFields" :key="field.key">
            {{ field.label }}：{{ field.value }}
          </span>
        </div>
        <div class="article-content">
          <p v-for="(paragraph, idx) in articleParagraphs" :key="idx" class="article-paragraph">
            {{ paragraph }}
          </p>
        </div>
        <div v-if="articleExtraFields.length" class="article-extra-meta">
          <span v-for="field in articleExtraFields" :key="field.key" class="article-extra-item">
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
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import { fetchCatalogFilters, fetchCatalogPolicies, fetchTopicChildren } from '../api/catalog'
import { fetchPolicyDetail } from '../api/graph'
import { focusPolicyDeconstruct, focusPolicyForGraph } from '../composables/policyGraphContext'

const props = defineProps({
  title: { type: String, default: '政策目录' },
  /** org：发布机构筛选；topic：主题词筛选 */
  mode: { type: String, default: 'org' },
})

const isOrgMode = computed(() => props.mode === 'org')

const orgColumns = [
  { key: 'fileName', label: '文件名称' },
  { key: 'publishDate', label: '发文日期' },
  { key: 'responsible', label: '责任机构或人' },
]
const topicColumns = [
  { key: 'fileName', label: '文件名称' },
  { key: 'publishDate', label: '发文日期' },
  { key: 'publishLevel', label: '发文级别' },
  { key: 'topicKeyword', label: '主题词' },
]
const tableColumns = computed(() => {
  if (isOrgMode.value) return orgColumns
  const hasTopicFilter = Boolean(selectedTopic.value || selectedTopicChild.value)
  if (hasTopicFilter) {
    return topicColumns.filter((c) => c.key !== 'topicKeyword')
  }
  return topicColumns
})
const antColumns = computed(() =>
  tableColumns.value.map((c) => ({
    title: c.label,
    dataIndex: c.key,
    key: c.key,
    width:
      c.key === 'publishDate'
        ? 160
        : c.key === 'fileName'
          ? isOrgMode.value
            ? 520
            : 560
          : isOrgMode.value
            ? 260
            : 220,
    className: c.key === 'publishDate' ? 'col-date' : c.key === 'fileName' ? 'col-title' : 'col-meta',
    customRender: ({ text }) => text || '—',
  })),
)

const filtersLoading = ref(true)
const loadError = ref('')
const organizations = ref([])
const regions = ref([])
const topics = ref([])

const selectedOrg = ref('')
const selectedRegion = ref('')
const selectedTopic = ref('')
const selectedTopicChild = ref('')
const topicChildren = ref([])
const page = ref(1)
const pageSize = 20

const tableLoading = ref(false)
const tableError = ref('')
const items = ref([])
const total = ref(0)
const choiceModalOpen = ref(false)
const detailModalOpen = ref(false)
const detailLoading = ref(false)
const pendingRow = ref(null)
const currentDetail = ref(null)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

const listModeParam = computed(() => (isOrgMode.value ? 'organization' : 'topic'))
const articleMetaConfig = [
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
const articleMetaFields = computed(() =>
  articleMetaConfig
    .map((field) => ({
      ...field,
      value: resolvedDetailValue(field.key),
    }))
    .filter((field) => field.value),
)
const articleExtraConfig = [
  { key: '网址', label: '网址' },
  { key: '来源', label: '来源' },
  { key: '有效性', label: '有效性' },
  { key: '附件', label: '附件' },
]
const articleExtraFields = computed(() =>
  articleExtraConfig
    .map((field) => ({
      ...field,
      value: resolvedDetailValue(field.key),
    }))
    .filter((field) => field.value),
)
const articleParagraphs = computed(() => {
  const content = resolvedDetailValue('正文')
  if (!content) return ['暂无正文内容']
  const paragraphs = content
    .split(/\r?\n+/)
    .map((x) => x.trim())
    .filter(Boolean)
  return paragraphs.length ? paragraphs : [content]
})

function onFilterChange() {
  page.value = 1
  loadPolicies()
}

function selectTopic(t) {
  selectedTopic.value = selectedTopic.value === t ? '' : t
  selectedTopicChild.value = ''
  page.value = 1
  loadTopicChildren()
  loadPolicies()
}

function clearTopic() {
  selectedTopic.value = ''
  selectedTopicChild.value = ''
  topicChildren.value = []
  page.value = 1
  loadPolicies()
}

function selectTopicChild(name) {
  selectedTopicChild.value = selectedTopicChild.value === name ? '' : name
  page.value = 1
  loadPolicies()
}

function goPage(p) {
  page.value = p
  loadPolicies()
}
function tableRowProps(record) {
  return {
    style: 'cursor:pointer',
    onClick: () => onRowClick(record),
  }
}

function onRowClick(row) {
  pendingRow.value = row
  choiceModalOpen.value = true
}

function openGraphView() {
  choiceModalOpen.value = false
  if (pendingRow.value?.id) {
    focusPolicyForGraph(pendingRow.value.id, pendingRow.value.fileName)
  }
}

function openDeconstructView() {
  choiceModalOpen.value = false
  if (pendingRow.value?.id) {
    focusPolicyDeconstruct(pendingRow.value.id, pendingRow.value.fileName)
  }
}

async function openOriginalView() {
  if (!pendingRow.value?.id) return
  choiceModalOpen.value = false
  detailModalOpen.value = true
  detailLoading.value = true
  try {
    currentDetail.value = await fetchPolicyDetail(pendingRow.value.id)
  } catch (e) {
    detailModalOpen.value = false
    message.error(e.response?.data?.error || e.message || '原文读取失败')
  } finally {
    detailLoading.value = false
  }
}

function normalizeDetailValue(value) {
  if (value == null) return ''
  const text = String(value).trim()
  if (!text) return ''
  if (/^[-—_\]\[()（）]+$/.test(text)) return ''
  return text
}

function resolvedDetailValue(key) {
  const detail = currentDetail.value?.detail || {}
  const aliasKey = key.replace('发文机构', '发布机构')
  const candidateKeys = Array.from(new Set([key, aliasKey, ...key.split('\\'), ...aliasKey.split('\\')].filter(Boolean)))

  for (const candidateKey of candidateKeys) {
    const value = normalizeDetailValue(detail[candidateKey])
    if (value) return value
  }
  return ''
}

function detailValue(key) {
  return resolvedDetailValue(key) || '—'
}

async function loadPolicies() {
  tableLoading.value = true
  tableError.value = ''
  try {
    const data = await fetchCatalogPolicies({
      listMode: listModeParam.value,
      organization: isOrgMode.value ? selectedOrg.value || undefined : undefined,
      sourceRegion: isOrgMode.value ? selectedRegion.value || undefined : undefined,
      category: !isOrgMode.value ? selectedTopic.value || undefined : undefined,
      topicChild: !isOrgMode.value ? selectedTopicChild.value || undefined : undefined,
      page: page.value,
      pageSize,
    })
    items.value = data.items || []
    total.value = data.total ?? 0
  } catch (e) {
    tableError.value = e.response?.data?.error || e.message || '加载失败'
    items.value = []
    total.value = 0
  } finally {
    tableLoading.value = false
  }
}

async function loadTopicChildren() {
  if (!selectedTopic.value) {
    topicChildren.value = []
    return
  }
  try {
    const data = await fetchTopicChildren(selectedTopic.value)
    topicChildren.value = data.items || []
  } catch {
    topicChildren.value = []
  }
}

onMounted(async () => {
  try {
    const data = await fetchCatalogFilters()
    organizations.value = data.organizations || []
    regions.value = data.regions || []
    topics.value = data.topics || []
  } catch (e) {
    loadError.value = e.response?.data?.error || e.message || '加载失败'
  } finally {
    filtersLoading.value = false
  }
  if (!loadError.value) {
    await loadPolicies()
  }
})

function childChipClass(i) {
  const scale = ['chip-sub-1', 'chip-sub-2', 'chip-sub-3', 'chip-sub-4', 'chip-sub-5']
  return scale[i % scale.length]
}
function topicChipClass(i) {
  const scale = ['chip-top-1', 'chip-top-2', 'chip-top-3', 'chip-top-4', 'chip-top-5', 'chip-top-6']
  return scale[i % scale.length]
}
</script>

<style scoped>
.catalog {
  max-width: 1200px;
  margin: 0 auto;
}
.page-title {
  margin: 0 0 16px;
  font-size: 18px;
  color: #111827;
}
.err {
  color: #b91c1c;
  margin: 0 0 12px;
}
.muted {
  color: #6b7280;
  font-size: 13px;
}
.loading-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 10px 0;
}
.toolbar {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px 14px;
  margin-bottom: 14px;
}
.toolbar-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px 16px;
  align-items: end;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}
.label {
  font-size: 13px;
  color: #374151;
  font-weight: 500;
}
.select { width: 100%; }
.topics-block {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px 14px;
  margin-bottom: 14px;
}
.topics-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.link {
  border: none;
  background: none;
  color: #3E2723;
  cursor: pointer;
  font-size: 13px;
  padding: 0;
}
.link:hover {
  text-decoration: underline;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.chip {
  border: 1px solid #e5e7eb !important;
  background:hsl(17, 26.50%, 61.60%) !important;
  color:rgb(255, 255, 255) !important;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 12px;
  line-height: 1.3;
}
.chip:hover {
  border-color: #7C8A8C !important;
  background: #f3f4f6 !important;
}
.chip.active {
  border-color: #3E2723 !important;
  background: #dbeafe !important;
  color: #111111 !important;
}
.topic-children {
  margin-top: 10px;
}
.chip-sub {
  border-color: transparent;
}
.chip-top-1 { background: #9DBAD5 !important; }
.chip-top-2 { background: #A3B18A !important; }
.chip-top-3 { background: #B8AB8E !important; }
.chip-top-4 { background: #B67162 !important; }
.chip-top-5 { background: #D4B38B !important; }
.chip-top-6 { background: #AA94C8 !important; }
.chip-sub-1 {
  background:rgb(132, 163, 132);
  color:rgb(116, 157, 121);
}
.chip-sub-2 {
  background: #A3B18A;
  color:rgb(255, 255, 255);
}
.chip-sub-3 {
  background: #B8AB8E;
  color:rgb(255, 255, 255);
}
.chip-sub-4 {
  background: #B67162;
  color:rgb(255, 255, 255);
}
.chip-sub-5 {
  background: #D4B38B;
  color:rgb(255, 255, 255);
}
.table-wrap {
  background: #fff;
  border: 1px solidrgb(255, 255, 255);
  border-radius: 8px;
  padding: 12px;
  overflow: auto;
}
.table-wrap :deep(.ant-table) {
  table-layout: fixed;
}
.table-wrap :deep(.ant-table-thead > tr > th.col-date),
.table-wrap :deep(.ant-table-tbody > tr > td.col-date) {
  white-space: nowrap;
}
.table-wrap :deep(.ant-table-thead > tr > th.col-title),
.table-wrap :deep(.ant-table-tbody > tr > td.col-title) {
  min-width: 0;
}
.table-wrap :deep(.ant-table-tbody > tr > td.col-title) {
  word-break: break-word;
}
.table-wrap :deep(.ant-table-thead > tr > th.col-meta),
.table-wrap :deep(.ant-table-tbody > tr > td.col-meta) {
  white-space: nowrap;
}
.empty {
  padding: 16px 0 8px;
}
.pager {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 12px;
  flex-wrap: wrap;
}
.choice-actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.choice-actions-triple {
  gap: 10px;
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
.article-extra-item {
  word-break: break-all;
}
.article-extra-item a {
  color: inherit;
  text-decoration: none;
}
.article-extra-item a:hover {
  text-decoration: underline;
}
</style>
