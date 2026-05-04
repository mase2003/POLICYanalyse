<template>
  <section class="panel">
    <h3>{{ title }}</h3>
    <ul>
      <li v-for="item in items" :key="item">{{ item }}</li>
    </ul>
  </section>
</template>

<script setup>
defineProps({
  title: { type: String, default: '政策预测' },
})

const items = ['政策热度趋势', '主题词趋势', '区域影响趋势']
</script>

<style scoped>
.panel {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px;
}
li {
  line-height: 1.8;
}
</style>
