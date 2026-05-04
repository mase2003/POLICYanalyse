<template>
  <section class="panel">
    <h3>{{ title }}</h3>
    <a-table :columns="columns" :data-source="tableData" :pagination="false" row-key="name" />
  </section>
</template>

<script setup>
defineProps({
  title: { type: String, default: '政策列表' },
})

const tableData = [
  {
    date: '2015/7/8',
    name: '关于修改《关于支持高等学校科技人员和学生科技创业专项资金管理办法（试行）》的通知',
    address: '各相关单位',
  },
  {
    date: '2015/5/5',
    name: '关于北京市服务业扩大开放综合试点总体方案的批复',
    address: '文化部、财政部、新闻出版广电总局、体育总局',
  },
  {
    date: '2015/2/9',
    name: '政府和社会资本合作项目政府采购管理办法',
    address: '北京市财政局',
  },
]
const columns = [
  { title: '发文日期', dataIndex: 'date', key: 'date' },
  { title: '发文名称', dataIndex: 'name', key: 'name' },
  { title: '责任机构', dataIndex: 'address', key: 'address' },
]
</script>

<style scoped>
.panel {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px;
}
</style>
