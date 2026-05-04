<template>
  <section class="panel">
    <div class="head">
      <h3>政策内容管理</h3>
    </div>

    <div class="toolbar">
      <a-input v-model:value="keyword" placeholder="按标题/网址/文号筛选" @pressEnter="loadList(1)" />
      <a-button type="primary" :loading="loading" @click="loadList(1)">查询</a-button>
      <a-popconfirm title="确认删除勾选政策节点？" @confirm="removeSelectedNodes">
        <a-button danger :disabled="!selectedNodeIds.length">批量删除</a-button>
      </a-popconfirm>
    </div>

    <a-table
      row-key="id"
      :columns="columns"
      :data-source="items"
      :pagination="false"
      :loading="loading"
      size="middle"
      :row-selection="nodeRowSelection"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'action'">
          <a-space>
            <a-button size="small" @click="openDetail(record.id)">查看</a-button>
            <a-popconfirm title="确认删除该政策节点？" @confirm="removeNode(record.id)">
              <a-button size="small" danger>删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <div class="pager">
      <span>共 {{ total }} 条</span>
      <a-pagination :current="page" :total="total" :page-size="pageSize" :show-size-changer="false" @change="loadList" />
    </div>

    <a-drawer v-model:open="detailOpen" title="政策内容详情管理" width="1080">
      <div v-if="detailLoading" class="loading">加载中…</div>
      <template v-else-if="detail">
       <div style="display: flex; align-items: center; gap: 12px;">
           <h4 style="margin: 0;">节点ID：{{ detail.id }}</h4>
             <a-button size="small" type="default" @click="bulkStripClosingBrackets">
             批量去除字段值杂乱值
                </a-button>
        </div>

        <a-table row-key="key" :columns="fieldColumns" :data-source="propertyRows" :pagination="false" size="small">
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'value'">
              <a-textarea v-model:value="editableValues[record.key]" :auto-size="{ minRows: 1, maxRows: 3 }" />
            </template>
            <template v-else-if="column.key === 'action'">
              <a-space>
                <a-button size="small" type="primary" @click="saveOneField(record.key)">保存</a-button>
                <a-popconfirm title="确认删除字段？" @confirm="removeField(record.key)">
                  <a-button size="small" danger>删字段</a-button>
                </a-popconfirm>
              </a-space>
            </template>
          </template>
        </a-table>
         
        <div class="sec-head">
          <h4 class="sec-title">关联节点</h4>
          <a-popconfirm title="确认删除勾选关系？" @confirm="removeSelectedRelations">
            <a-button size="small" danger :disabled="!selectedRelationIds.length">批量删除已选</a-button>
          </a-popconfirm>
        </div>
        <a-table
          row-key="relId"
          :columns="relColumns"
          :data-source="detail.relations || []"
          :pagination="{ pageSize: 8 }"
          size="small"
          :row-selection="relationRowSelection"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'neighbor'">
              {{ renderNeighbor(record) }}
            </template>
            <template v-else-if="column.key === 'action'">
              <a-popconfirm title="确认删除该关联关系？" @confirm="removeRelation(record.relId)">
                <a-button size="small" danger>删关系</a-button>
              </a-popconfirm>
            </template>
          </template>
        </a-table>
      </template>
    </a-drawer>

    <div v-if="locked" class="unlock-mask">
      <div class="unlock-card">
        <h4>政策内容管理已锁定</h4>
        <p>请输入6位密码/每天刷新</p>
        <a-input-password v-model:value="unlockPassword" maxlength="6" placeholder="请输入6位数字密码" @pressEnter="doUnlock" />
        <div class="unlock-actions">
          <a-button @click="closeUnlock">关闭并返回首页</a-button>
          <a-button type="primary" :loading="unlocking" @click="doUnlock">解锁</a-button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { sidebarNavigateKey } from '../composables/policyGraphContext'
import {
  deletePolicyContentField,
  deletePolicyContentNode,
  deletePolicyContentRelation,
  deletePolicyContentRelations,
  fetchPolicyContentDetail,
  fetchPolicyContentList,
  setPolicyContentManagePassword,
  unlockPolicyContentManage,
  updatePolicyContentFields,
} from '../api/crawler'

const keyword = ref('')
const loading = ref(false)
const detailLoading = ref(false)
const detailOpen = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const detail = ref(null)
const editableValues = ref({})
const selectedRelationIds = ref([])
const selectedNodeIds = ref([])
const nodeSelectMode = ref('multiple')
const locked = ref(true)
const unlocking = ref(false)
const unlockPassword = ref('')

const columns = [
  { title: '标题', dataIndex: 'title', key: 'title' },
  { title: '发布日期', dataIndex: 'publishDate', key: 'publishDate', width: 140 },
  { title: '发文字号', dataIndex: 'docNo', key: 'docNo', width: 180 },
  { title: '操作', key: 'action', width: 160 },
]
const fieldColumns = [
  { title: '字段', dataIndex: 'key', key: 'key', width: 220 },
  { title: '值', dataIndex: 'value', key: 'value' },
  { title: '操作', key: 'action', width: 180 },
]
const relColumns = [
  { title: '关系ID', dataIndex: 'relId', key: 'relId', width: 100 },
  { title: '关系类型', dataIndex: 'type', key: 'type', width: 160 },
  { title: '方向', dataIndex: 'direction', key: 'direction', width: 90 },
  { title: '关联节点', key: 'neighbor' },
  { title: '操作', key: 'action', width: 120 },
]
const relationRowSelection = computed(() => ({
  preserveSelectedRowKeys: true,
  selectedRowKeys: selectedRelationIds.value,
  onChange: (keys) => {
    selectedRelationIds.value = keys
  },
}))
const nodeRowSelection = computed(() => ({
  type: nodeSelectMode.value === 'single' ? 'radio' : 'checkbox',
  preserveSelectedRowKeys: true,
  selectedRowKeys: selectedNodeIds.value,
  onChange: (keys) => {
    if (nodeSelectMode.value === 'single') {
      selectedNodeIds.value = keys.length ? [keys[keys.length - 1]] : []
      return
    }
    selectedNodeIds.value = [...keys]
  },
}))

const propertyRows = computed(() =>
  Object.entries(detail.value?.properties || {}).map(([key, value]) => ({
    key,
    value: value == null ? '' : String(value),
  })),
)

function renderNeighbor(record) {
  const p = record.neighborProperties || {}
  return p.name || p.标题 || p.文件名称 || `节点 ${record.neighborId}`
}

async function loadList(nextPage = page.value) {
  if (locked.value) return
  loading.value = true
  try {
    page.value = nextPage
    const data = await fetchPolicyContentList({
      q: keyword.value,
      page: page.value,
      pageSize,
    })
    items.value = data.items || []
    total.value = data.total || 0
  } catch (e) {
    message.error(e.response?.data?.error || e.message || '查询失败')
  } finally {
    loading.value = false
  }
}

async function removeSelectedNodes() {
  if (!selectedNodeIds.value.length) return
  const ids = [...selectedNodeIds.value]
  let removed = 0
  for (const id of ids) {
    try {
      await deletePolicyContentNode(id)
      removed += 1
    } catch {
      // 单条失败不中断批量
    }
  }
  selectedNodeIds.value = []
  message.success(`已删除 ${removed} 条政策节点`)
  await loadList(page.value)
}

async function openDetail(nodeId) {
  detailOpen.value = true
  detailLoading.value = true
  try {
    const data = await fetchPolicyContentDetail(nodeId)
    detail.value = data
    selectedRelationIds.value = []
    editableValues.value = Object.fromEntries(
      Object.entries(data.properties || {}).map(([k, v]) => [k, v == null ? '' : String(v)]),
    )
  } catch (e) {
    message.error(e.response?.data?.error || e.message || '详情读取失败')
  } finally {
    detailLoading.value = false
  }
}

async function bulkStripClosingBrackets() {
  if (!detail.value?.id) return
  const next = {}
  let changed = false
  for (const [k, v] of Object.entries(editableValues.value)) {
    const s = String(v ?? '')
    const stripped = s.replace(/\]/g, '')
    next[k] = stripped
    if (stripped !== s) changed = true
  }
  if (!changed) {
    message.info('当前字段值中未发现 ]')
    return
  }
  try {
    await updatePolicyContentFields(detail.value.id, next)
    message.success('已批量去除 ]')
    Object.assign(editableValues.value, next)
    await openDetail(detail.value.id)
  } catch (e) {
    message.error(e.response?.data?.error || e.message || '更新失败')
  }
}

async function saveOneField(field) {
  if (!detail.value?.id) return
  try {
    await updatePolicyContentFields(detail.value.id, { [field]: editableValues.value[field] ?? '' })
    message.success('字段已更新')
    await openDetail(detail.value.id)
  } catch (e) {
    message.error(e.response?.data?.error || e.message || '字段更新失败')
  }
}

async function removeField(field) {
  if (!detail.value?.id) return
  try {
    await deletePolicyContentField(detail.value.id, field)
    message.success('字段已删除')
    await openDetail(detail.value.id)
  } catch (e) {
    message.error(e.response?.data?.error || e.message || '字段删除失败')
  }
}

async function removeRelation(relId) {
  try {
    await deletePolicyContentRelation(relId)
    message.success('关系已删除')
    if (detail.value?.id) await openDetail(detail.value.id)
  } catch (e) {
    message.error(e.response?.data?.error || e.message || '关系删除失败')
  }
}

async function removeSelectedRelations() {
  if (!selectedRelationIds.value.length) return
  try {
    const out = await deletePolicyContentRelations(selectedRelationIds.value)
    message.success(`已删除 ${out.removed || 0} 条关系`)
    selectedRelationIds.value = []
    if (detail.value?.id) await openDetail(detail.value.id)
  } catch (e) {
    message.error(e.response?.data?.error || e.message || '批量删除关系失败')
  }
}

async function removeNode(nodeId) {
  try {
    await deletePolicyContentNode(nodeId)
    message.success('政策节点已删除')
    if (detail.value?.id === String(nodeId)) {
      detailOpen.value = false
      detail.value = null
    }
    selectedNodeIds.value = selectedNodeIds.value.filter((id) => String(id) !== String(nodeId))
    await loadList(page.value)
  } catch (e) {
    message.error(e.response?.data?.error || e.message || '节点删除失败')
  }
}

watch(nodeSelectMode, (mode) => {
  if (mode === 'single' && selectedNodeIds.value.length > 1) {
    selectedNodeIds.value = selectedNodeIds.value.slice(0, 1)
  }
})

loadList(1)

async function doUnlock() {
  unlocking.value = true
  try {
    await unlockPolicyContentManage(unlockPassword.value)
    setPolicyContentManagePassword(unlockPassword.value)
    unlockPassword.value = ''
    locked.value = false
    message.success('解锁成功')
    await loadList(1)
  } catch (e) {
    message.error(e.response?.data?.error || e.message || '解锁失败')
  } finally {
    unlocking.value = false
  }
}

function closeUnlock() {
  sidebarNavigateKey.value = 'home'
}
</script>

<style scoped>
.panel { background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; }
.head h3 { margin: 0; }
.head p { margin: 8px 0 0; color: #6b7280; font-size: 13px; }
.toolbar { margin: 14px 0; display: flex; gap: 10px; }
.pager { margin-top: 12px; display: flex; align-items: center; gap: 12px; }
.loading { color: #6b7280; padding: 12px 0; }
.field-toolbar { margin-bottom: 10px; }
.sec-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.sec-title { margin: 16px 0 8px; }
.unlock-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.46);
  z-index: 1500;
  display: flex;
  align-items: center;
  justify-content: center;
}
.unlock-card {
  width: min(460px, calc(100vw - 32px));
  background: #fff;
  border-radius: 10px;
  border: 1px solid #e5e7eb;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.unlock-card h4 {
  margin: 0;
}
.unlock-card p {
  margin: 0;
  color: #6b7280;
  font-size: 13px;
}
.unlock-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
