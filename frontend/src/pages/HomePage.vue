<!--
  首页：数据一次性从 /api/home/dashboard 拉取，子块无独立请求，减少等待与闪烁。
  样式采用 CSS Grid，便于后续加列或改断点。
-->
<template>
  <div class="home">
    <a-alert v-if="loadError" type="error" :message="loadError" show-icon />
    <div v-else-if="loading" class="loading-wrap">
      <a-spin size="large" />
      <p class="loading">首页数据加载中…</p>
    </div>

    <template v-else>
      <section class="grid-top">
        <div class="cell carousel-cell">
          <HomeCarousel :slides="carouselSlides" />
        </div>
      </section>

      <section class="grid-middle">
        <a-card class="cell" :bordered="false">
          <PolicyMiniList title="最新政策推荐" :columns="latestCols" :items="latestRows" row-clickable @row-click="onPolicyRow" />
        </a-card>
      </section>

      <section class="grid-bottom">
        <a-card class="cell" :bordered="false">
          <template #title>已收录政策类型</template>
          <HomePieChart :series="pieSeries" :topic-labels="pieTopicOrder" />
        </a-card>
        <a-card class="cell" :bordered="false">
          <PolicyMiniList
            title="热门检索政策"
            :columns="hotCols"
            :items="hotRows"
            row-clickable
            @row-click="onPolicyRow"
          />
        </a-card>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { fetchHomeDashboard } from '../api/home'
import { focusPolicyForGraph } from '../composables/policyGraphContext'
import HomeCarousel from '../components/home/HomeCarousel.vue'
import HomePieChart from '../components/home/HomePieChart.vue'
import PolicyMiniList from '../components/home/PolicyMiniList.vue'

const loading = ref(true)
const loadError = ref('')
const dashboard = ref(null)

const carouselSlides = computed(() => dashboard.value?.carousel || [])
const pieSeries = computed(() => dashboard.value?.pie || [])
/** 与政策目录「主题词」同一套枚举，仅用于饼图下方标签文案（无数字） */
const pieTopicOrder = computed(() => dashboard.value?.pieTopicOrder || [])
const hotRows = computed(() => dashboard.value?.hot || [])
const latestRows = computed(() => dashboard.value?.latest || [])

const hotCols = [
  { key: 'title', label: '政策名称' },
  { key: 'searchCount', label: '搜索次数' },
]
const latestCols = [
  { key: 'title', label: '政策名称' },
  { key: 'publishDate', label: '发表日期' },
]

function onPolicyRow(row) {
  if (row?.id) focusPolicyForGraph(row.id, row.title)
}

onMounted(async () => {
  try {
    dashboard.value = await fetchHomeDashboard()
  } catch (e) {
    loadError.value = e.response?.data?.error || e.message || '加载失败'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.home {
  max-width: 1200px;
  margin: 0 auto;
}
.loading-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 20px 8px;
}
.loading {
  color: #6b7280;
  margin: 0;
}
.grid-top {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
  margin-bottom: 16px;
}
.grid-bottom {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.grid-middle {
  margin: 16px 0;
}
.cell {
  min-width: 0;
}
.carousel-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
}
@media (max-width: 900px) {
  .grid-top,
  .grid-bottom {
    grid-template-columns: 1fr;
  }
}
</style>
