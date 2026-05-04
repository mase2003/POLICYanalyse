<template>
  <section v-if="variant === 'policyArticle'" class="kg-page mode-policy">
    <div v-if="!graphFocusNodeId" class="policy-wait">
      <p class="policy-wait-title">尚未选择政策</p>
      <p class="policy-wait-text">请先在首页、政策目录或搜索结果中选择一条政策。</p>
    </div>

    <template v-else>
      <div class="policy-toolbar">
        <div class="policy-banner">
          当前政策：<strong>{{ graphFocusTitle || '（无标题）' }}</strong>
        </div>
        <a-button @click="drawerOpen = true">展开文本信息</a-button>
      </div>
      <div v-if="errorMsg" class="alert err">{{ errorMsg }}</div>
      <div class="graph-panel policy-graph">
        <div v-if="loading" class="loading-mask">
          <div class="spinner" />
          <p>正在加载图谱…</p>
        </div>
        <D3Graph
          v-show="!policyGraphEmpty"
          :nodes="nodes"
          :edges="edges"
          :policy-mode="variant === 'policyArticle'"
          @node-click="onNodeClick"
          @expand-node="onExpandFromBubble"
        />
        <div v-if="policyGraphEmpty && !loading" class="empty">
          <p>暂无邻接关系。</p>
        </div>
      </div>
    </template>
  </section>

  <section v-else class="kg-page">
    <div class="kg-head">
      <div class="kg-head-row">
        <span class="kg-label">输入查询语句进行查询:</span>
      </div>
      <a-textarea
        v-model:value="query"
        class="kg-query"
        :rows="3"
        :auto-size="{ minRows: 3, maxRows: 8 }"
        spellcheck="false"
        placeholder="只读 Cypher，须以 MATCH / OPTIONAL MATCH / WITH / UNWIND / RETURN 开头"
        @keydown.ctrl.enter="loadGraph"
      />
      <div class="kg-actions">
        <a-button type="primary" :loading="loading" :disabled="loading" @click="loadGraph">
          {{ loading ? '查询中…' : '执行查询' }}
        </a-button>
        <a-button :disabled="loading" @click="resetView">重置</a-button>
        <a-button @click="refreshStatus">刷新连接状态</a-button>
      </div>
    </div>

    <div v-if="errorMsg" class="alert err">{{ errorMsg }}</div>
    <div v-else-if="hint" class="alert hint">{{ hint }}</div>

    <div class="meta-row">
      <span>
        分页状态：本批展示 <strong>{{ edges.length }}</strong> 条边 / 图总边数
        <strong>{{ total }}</strong>
      </span>
      <span v-if="cursor != null"> · 游标 {{ cursor }}</span>
      <span v-if="hasMore" class="warn"> · 已截断，请用搜索或点击节点扩展</span>
      <span v-if="lastLoadedAt" class="muted"> · 上次加载 {{ lastLoadedAt }}</span>
    </div>

    <div class="graph-panel">
      <div v-if="loading" class="loading-mask">
        <div class="spinner" />
        <p>正在加载图谱…</p>
      </div>
      <D3Graph
        v-show="!emptyState"
        :nodes="nodes"
        :edges="edges"
        :policy-mode="false"
        @node-click="onNodeClick"
        @expand-node="onExpandFromBubble"
      />
      <div v-if="emptyState && !loading" class="empty">
        <p>暂无图数据，请确认 Neo4j 已连接且 Cypher 能返回路径或关系。</p>
        <p class="muted">提示：仅展示最多 300 条边；若库很大，请缩小 MATCH 或 LIMIT 扫描范围。</p>
      </div>
    </div>

    <div class="search-block">
      <span class="kg-label">超出部分请搜索节点：</span>
      <div class="kg-actions">
        <a-input v-model:value="keyword" class="kg-input" placeholder="关键词" @pressEnter="doSearch" />
        <a-button type="primary" :loading="searchLoading" :disabled="searchLoading" @click="doSearch">
          {{ searchLoading ? '搜索中…' : '搜索' }}
        </a-button>
      </div>
      <div v-if="searchResults.length" class="result">
        <h4>搜索结果</h4>
        <ul>
          <li v-for="item in searchResults" :key="item.id">
            <span>{{ item.properties?.name || item.id }}</span>
            <a-button type="link" @click="expandById(item.id)">扩展</a-button>
          </li>
        </ul>
      </div>
    </div>
  </section>

  <a-drawer v-model:open="drawerOpen" title="文本信息" placement="right" width="980">
    <div class="article-reader drawer-reader">
      <h3 class="article-title">{{ detailValue(policyDetail, '标题') }}</h3>
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
      <div v-if="policyExplainText" class="policy-explain-section">
        <h4 class="policy-explain-title">政策拆解</h4>
        <pre class="policy-explain-body">{{ policyExplainText }}</pre>
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
  </a-drawer>

  <a-modal v-model:open="nodeModalOpen" title="节点内容" width="820px" :footer="null">
    <div class="detail-grid">
      <div v-for="item in activeNodeEntries" :key="item.key" class="detail-item">
        <div class="detail-label">{{ item.key }}</div>
        <div class="detail-value">{{ item.value }}</div>
      </div>
    </div>
    <div class="modal-actions">
      <a-button type="primary" @click="expandActiveNode">扩展关联节点</a-button>
    </div>
  </a-modal>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import D3Graph from '../components/graph/D3Graph.vue'
import { reportSearchHit } from '../api/home'
import { expandNode, fetchGraphStatus, fetchNodeDetail, fetchPolicyDetail, queryGraph, searchGraph } from '../api/graph'
import { graphFocusNodeId, graphFocusTitle } from '../composables/policyGraphContext'

const props = defineProps({
  title: { type: String, default: '' },
  /** default：完整 Cypher 探索；policyArticle：仅从其他页选中节点后展示图谱 */
  variant: { type: String, default: 'default' },
})

const query = ref('MATCH p=(n)-[r]->(m) RETURN p LIMIT 5000')
const keyword = ref('')
const nodes = ref([])
const edges = ref([])
const total = ref(0)
const hasMore = ref(false)
const cursor = ref(0)
const searchResults = ref([])
const errorMsg = ref('')
const hint = ref('')
const loading = ref(false)
const searchLoading = ref(false)
const lastLoadedAt = ref('')
const drawerOpen = ref(false)
const nodeModalOpen = ref(false)
const policyDetail = ref(null)
const activeNodeDetail = ref(null)
const activeNodeId = ref(null)

const status = ref({ checked: false, neo4j_connected: false, hint: '' })
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
      value: resolvedDetailValue(policyDetail.value, field.key),
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
      value: resolvedDetailValue(policyDetail.value, field.key),
    }))
    .filter((field) => field.value),
)
const articleParagraphs = computed(() => {
  const content = resolvedDetailValue(policyDetail.value, '正文')
  if (!content) return ['暂无正文内容']
  const paragraphs = content
    .split(/\r?\n+/)
    .map((x) => x.trim())
    .filter(Boolean)
  return paragraphs.length ? paragraphs : [content]
})

const policyExplainText = computed(() => resolvedDetailValue(policyDetail.value, '政策拆解全文'))

let statusTimer

const emptyState = computed(
  () => nodes.value.length === 0 && edges.value.length === 0,
)

const policyGraphEmpty = computed(
  () => props.variant === 'policyArticle' && emptyState.value,
)
const activeNodeEntries = computed(() => {
  const props = activeNodeDetail.value?.properties || {}
  const entries = Object.entries(props).map(([key, value]) => ({
    key,
    value: value == null || value === '' ? '—' : String(value),
  }))
  if (!entries.length) {
    return [{ key: '节点信息', value: '暂无可展示内容' }]
  }
  return entries
})

function mergeGraph(payload) {
  const nodeMap = new Map(nodes.value.map((n) => [n.id, n]))
  const edgeMap = new Map(edges.value.map((e) => [e.id, e]))
  ;(payload.nodes || []).forEach((n) => nodeMap.set(n.id, n))
  ;(payload.edges || []).forEach((e) => edgeMap.set(e.id, e))
  nodes.value = [...nodeMap.values()]
  edges.value = [...edgeMap.values()]
  total.value = payload.total ?? edges.value.length
  hasMore.value = Boolean(payload.has_more)
  cursor.value = payload.cursor ?? Math.min(300, total.value)
}

function apiErrorMessage(err) {
  const d = err.response?.data
  if (typeof d === 'string') return d
  if (d?.error) return d.error
  return err.message || '请求失败'
}

async function refreshStatus() {
  try {
    const data = await fetchGraphStatus()
    status.value = {
      checked: true,
      neo4j_connected: Boolean(data.neo4j_connected),
      hint: data.hint || '',
    }
    if (!status.value.neo4j_connected) {
      hint.value =
        data.hint ||
        '数据库未连通，请查看下方说明并确认 Neo4j 已启动、.env 中账号密码正确且已重启 Flask。'
    } else {
      hint.value = ''
    }
  } catch (e) {
    status.value = {
      checked: true,
      neo4j_connected: false,
      hint: '',
    }
    hint.value = '无法访问后端 /api/graph/status，请确认 Flask 已在本机启动（默认端口 5005）。'
  }
}

async function loadGraph() {
  errorMsg.value = ''
  hint.value = ''
  loading.value = true
  try {
    const data = await queryGraph(query.value, 300)
    nodes.value = data.nodes || []
    edges.value = data.edges || []
    total.value = data.total ?? edges.value.length
    hasMore.value = Boolean(data.has_more)
    cursor.value = data.cursor ?? 0
    lastLoadedAt.value = new Date().toLocaleString()
  } catch (err) {
    errorMsg.value = apiErrorMessage(err)
  } finally {
    loading.value = false
  }
}

function resetView() {
  errorMsg.value = ''
  hint.value = ''
  query.value = 'MATCH p=(n)-[r]->(m) RETURN p LIMIT 5000'
  nodes.value = []
  edges.value = []
  total.value = 0
  hasMore.value = false
  cursor.value = 0
  searchResults.value = []
  lastLoadedAt.value = ''
}

async function doSearch() {
  errorMsg.value = ''
  searchLoading.value = true
  try {
    const data = await searchGraph(keyword.value, 20)
    searchResults.value = data.items || []
  } catch (err) {
    errorMsg.value = apiErrorMessage(err)
  } finally {
    searchLoading.value = false
  }
}

async function expandById(id) {
  errorMsg.value = ''
  loading.value = true
  try {
    reportSearchHit(String(id)).catch(() => {})
    const data = await expandNode(id, 1, 100)
    mergeGraph(data)
    lastLoadedAt.value = new Date().toLocaleString()
  } catch (err) {
    errorMsg.value = apiErrorMessage(err)
  } finally {
    loading.value = false
  }
}

async function onExpandFromBubble(node) {
  if (!node?.id) return
  await expandById(node.id)
}

async function loadPolicyDetail(id) {
  if (!id) {
    policyDetail.value = null
    return
  }
  try {
    policyDetail.value = await fetchPolicyDetail(id)
  } catch {
    policyDetail.value = null
  }
}

watch(
  () => [props.variant, graphFocusNodeId.value],
  async () => {
    if (props.variant !== 'policyArticle') return
    const id = graphFocusNodeId.value
    errorMsg.value = ''
    if (!id) {
      nodes.value = []
      edges.value = []
      total.value = 0
      hasMore.value = false
      cursor.value = 0
      return
    }
    nodes.value = []
    edges.value = []
    await loadPolicyDetail(id)
    await expandById(id)
  },
  { immediate: true },
)

watch(drawerOpen, (open) => {
  if (open && props.variant === 'policyArticle' && graphFocusNodeId.value) {
    loadPolicyDetail(graphFocusNodeId.value)
  }
})

async function onNodeClick(node) {
  activeNodeId.value = node.id
  try {
    activeNodeDetail.value = await fetchNodeDetail(node.id)
  } catch {
    activeNodeDetail.value = { properties: node.properties || {} }
  }
  nodeModalOpen.value = true
}

function normalizeDetailValue(value) {
  if (value == null) return ''
  const text = String(value).trim()
  if (!text) return ''
  if (/^[-—_\]\[()（）]+$/.test(text)) return ''
  return text
}

function resolvedDetailValue(detail, key) {
  const values = detail?.detail || detail?.properties || {}
  const aliasKey = key.replace('发文机构', '发布机构')
  const candidateKeys = Array.from(new Set([key, aliasKey, ...key.split('\\'), ...aliasKey.split('\\')].filter(Boolean)))

  for (const candidateKey of candidateKeys) {
    const value = normalizeDetailValue(values[candidateKey])
    if (value) return value
  }
  return ''
}

function detailValue(detail, key) {
  return resolvedDetailValue(detail, key) || '—'
}

async function expandActiveNode() {
  if (!activeNodeId.value) return
  nodeModalOpen.value = false
  await expandById(activeNodeId.value)
}

onMounted(async () => {
  await refreshStatus()
  statusTimer = setInterval(refreshStatus, 20000)
  if (props.variant === 'policyArticle' && !graphFocusNodeId.value) {
    hint.value = ''
  }
})

onUnmounted(() => {
  if (statusTimer) clearInterval(statusTimer)
})
</script>

<style scoped>
.kg-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.kg-head {
  background: #fff;
  padding: 12px 16px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.06);
}

.kg-head-row {
  margin-bottom: 8px;
}

.kg-label {
  font-size: 14px;
  color: #374151;
}

.kg-query {
  width: 100%;
  font-family: ui-monospace, Consolas, monospace;
  font-size: 13px;
  padding: 10px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  resize: vertical;
  min-height: 72px;
}

.kg-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
  align-items: center;
}

.kg-input {
  padding: 8px 10px;
  min-width: 220px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
}

.status-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  padding: 8px 12px;
  background: #f9fafb;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #9ca3af;
}

.dot.ok {
  background: #22c55e;
}

.dot.failed {
  background: #ef4444;
}

.muted {
  color: #6b7280;
  font-size: 12px;
}

.meta-row {
  font-size: 13px;
  color: #374151;
}

.warn {
  color: #b45309;
}

.alert {
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 13px;
}

.alert.err {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
}

.alert.hint {
  background: #fffbeb;
  border: 1px solid #fde68a;
  color: #92400e;
}

.graph-panel {
  position: relative;
  min-height: 400px;
}

.loading-mask {
  position: absolute;
  inset: 0;
  z-index: 2;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.75);
  border-radius: 8px;
  gap: 8px;
}

.spinner {
  width: 36px;
  height: 36px;
  border: 3px solid #e5e7eb;
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.empty {
  padding: 32px;
  text-align: center;
  color: #4b5563;
  background: #fff;
  border: 1px dashed #d1d5db;
  border-radius: 8px;
}

.search-block {
  background: #fff;
  padding: 12px 16px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
}

.result {
  margin-top: 12px;
}

.result ul {
  list-style: none;
  padding: 0;
  margin: 8px 0 0;
}

.result li {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 6px 0;
  border-bottom: 1px solid #f3f4f6;
}

.mode-policy .policy-wait {
  padding: 40px 24px;
  text-align: center;
  background: #fff;
  border: 1px dashed #d1d5db;
  border-radius: 8px;
  color: #4b5563;
}
.policy-wait-title {
  margin: 0 0 10px;
  font-size: 16px;
  font-weight: 600;
  color: #111827;
}
.policy-wait-text {
  margin: 0;
  font-size: 14px;
  line-height: 1.65;
  max-width: 520px;
  margin-left: auto;
  margin-right: auto;
}
.policy-banner {
  font-size: 14px;
  color: #374151;
}
.policy-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.policy-graph {
  min-height: 420px;
}
.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.article-reader {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.article-title {
  margin: 0;
  font-size: 24px;
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
.policy-explain-section {
  padding: 12px;
  border: 1px solid #C0D1C2;
  border-radius: 8px;
  background: #E1E9E2;
}
.policy-explain-title {
  margin: 0 0 10px;
  font-size: 15px;
  font-weight: 600;
  color: #4F6F52;
}
.policy-explain-body {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color:rgb(26, 54, 41);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 50vh;
  overflow: auto;
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
.detail-item {
  border: 1px solid #eef2f7;
  border-radius: 8px;
  padding: 12px;
  background: #fafcff;
}
.detail-label {
  margin-bottom: 8px;
  color: #64748b;
  font-size: 12px;
}
.detail-value {
  white-space: pre-wrap;
  word-break: break-word;
  color: #0f172a;
  line-height: 1.6;
}
.modal-actions {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
