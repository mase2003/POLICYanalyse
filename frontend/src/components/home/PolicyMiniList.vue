<!-- 政策简表：列由 props 配置，便于扩展 -->
<template>
  <div class="mini-list">
    <h4 class="title">{{ title }}</h4>
    <p v-if="hint" class="hint">{{ hint }}</p>
    <a-table
      :columns="antColumns"
      :data-source="items"
      :pagination="false"
      size="small"
      :row-key="(row, idx) => row.id ?? idx"
      :custom-row="customRow"
    />
    <p v-if="!items.length" class="empty">暂无数据</p>
  </div>
</template>

<script setup>
const props = defineProps({
  title: { type: String, required: true },
  columns: { type: Array, required: true },
  items: { type: Array, default: () => [] },
  hint: { type: String, default: '' },
  rowClickable: { type: Boolean, default: false },
})

const emit = defineEmits(['row-click'])
const antColumns = props.columns.map((c) => ({
  title: c.label,
  dataIndex: c.key,
  key: c.key,
}))

function onRow(row) {
  if (props.rowClickable) emit('row-click', row)
}
function customRow(record) {
  if (!props.rowClickable) return {}
  return { style: 'cursor:pointer', onClick: () => onRow(record) }
}
</script>

<style scoped>
.mini-list {

  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 12px 14px;
  height: 100%;
}
.title {
  margin: 0 0 10px;
  font-size: 16px;
  color: #111827;
}
.hint {
  margin: 0 0 8px;
  font-size: 12px;
  color: #6b7280;
}
.empty {
  color: #9ca3af;
  font-size: 13px;
  margin: 12px 0 0;
}
</style>
