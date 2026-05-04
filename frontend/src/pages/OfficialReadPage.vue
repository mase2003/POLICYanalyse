<template>
  <section class="panel">
    <h3 class="page-title">{{ title }}</h3>
    <div class="toolbar">
      <a-input v-model:value="keyword" class="input" placeholder="按政策解读标题搜索" allow-clear @pressEnter="reload(true)" />
      <a-date-picker
        v-model:value="datePickerValue"
        class="input"
        picker="month"
        value-format="YYYY-MM"
        placeholder="选择年月"
        @change="onDateChange"
      />
      <a-select
        v-model:value="organization"
        class="input"
        placeholder="全部机构"
        allow-clear
        :options="organizations.map((o) => ({ label: o, value: o }))"
        @change="reload(true)"
      />
      <a-button type="primary" @click="reload(true)">查询</a-button>
    </div>
    <a-alert v-if="errorMsg" type="error" :message="errorMsg" show-icon class="err-alert" />
    <div class="list-wrap">
      <a-table
        :columns="columns"
        :data-source="items"
        :pagination="false"
        row-key="id"
        :custom-row="tableRowProps"
      />
      <p v-if="!loading && !items.length" class="muted">暂无匹配解读文件。</p>
      <div v-if="total > 0" class="pager">
        <span class="muted">共 {{ total }} 条</span>
        <a-pagination
          size="small"
          :current="page"
          :total="total"
          :page-size="pageSize"
          :show-size-changer="false"
          @change="goPage"
        />
        <span class="muted">第 {{ page }} / {{ totalPages }} 页</span>
      </div>
    </div>
    <div v-if="detail" class="reader-modal-mask" @click.self="detail = null">
      <div class="reader">
        <div class="reader-head">
          <h4>{{ detail.title || '解读正文' }}</h4>
          <a-button class="btn-close" @click="detail = null">关闭</a-button>
        </div>
        <p class="meta">发布机构：{{ detail.organization || '—' }} · 发布日期：{{ detail.publishDate || '—' }}</p>
        <pre class="content">{{ detail.content || '暂无正文内容' }}</pre>
      </div>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { fetchOfficialReadDetail, fetchOfficialReadFilters, fetchOfficialReadList } from '../api/officialRead'

defineProps({
  title: { type: String, default: '官方解读' },
})

const keyword = ref('')
const datePrefix = ref('')
const datePickerValue = ref('')
const organization = ref('')
const organizations = ref([])
const items = ref([])
const detail = ref(null)
const loading = ref(false)
const errorMsg = ref('')
const page = ref(1)
const pageSize = 20
const total = ref(0)
const totalPages = ref(1)
const columns = [
  { title: '政策解读文件标题', dataIndex: 'title', key: 'title', customRender: ({ text }) => text || '—' },
  { title: '发布机构', dataIndex: 'organization', key: 'organization', customRender: ({ text }) => text || '—' },
  { title: '发布日期', dataIndex: 'publishDate', key: 'publishDate', customRender: ({ text }) => text || '—' },
]

async function reload(resetPage = false) {
  if (resetPage) page.value = 1
  loading.value = true
  errorMsg.value = ''
  try {
    const data = await fetchOfficialReadList({
      q: keyword.value || undefined,
      datePrefix: datePrefix.value || undefined,
      organization: organization.value || undefined,
      page: page.value,
      pageSize,
    })
    items.value = data.items || []
    total.value = Number(data.total || 0)
    totalPages.value = Math.max(1, Math.ceil(total.value / pageSize))
  } catch (e) {
    errorMsg.value = e.response?.data?.error || e.message || '加载失败'
    items.value = []
    total.value = 0
    totalPages.value = 1
  } finally {
    loading.value = false
  }
}

function onDateChange(value) {
  datePrefix.value = value || ''
  reload(true)
}

function goPage(next) {
  if (next < 1 || next > totalPages.value || next === page.value) return
  page.value = next
  reload(false)
}
function tableRowProps(record) {
  return {
    style: 'cursor:pointer',
    onClick: () => openDetail(record.id),
  }
}

async function openDetail(id) {
  try {
    detail.value = await fetchOfficialReadDetail(id)
  } catch (e) {
    errorMsg.value = e.response?.data?.error || e.message || '读取正文失败'
  }
}

onMounted(async () => {
  try {
    const f = await fetchOfficialReadFilters()
    organizations.value = f.organizations || []
  } catch {
    organizations.value = []
  }
  reload(true)
})
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
.toolbar {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) 240px 240px auto;
  gap: 8px;
  margin-bottom: 12px;
}
.input {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
}
.muted {
  font-size: 13px;
  color: #6b7280;
}
.pager {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 10px;
  flex-wrap: wrap;
}
.pager button {
  padding: 0;
}
.pager button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.reader {
  width: min(980px, calc(100vw - 40px));
  max-height: calc(100vh - 70px);
  overflow: auto;
  background: #fff;
  border-radius: 10px;
  border: 1px solid #e5e7eb;
  padding: 14px;
}
.reader-modal-mask {
  position: fixed;
  inset: 0;
  z-index: 60;
  background: rgba(15, 23, 42, 0.35);
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding-top: 28px;
}
.reader-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.btn-close {
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: #fff;
  padding: 6px 10px;
  cursor: pointer;
}
.meta {
  margin: 8px 0 12px;
  color: #6b7280;
  font-size: 13px;
}
.content {
  white-space: pre-wrap;
  font-size: 13px;
  line-height: 1.6;
  background: rgb(239, 232, 230);
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px;
}
.err-alert {
  margin: 0 0 8px;
}
</style>
