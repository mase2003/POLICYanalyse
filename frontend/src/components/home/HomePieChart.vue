<!-- ECharts 饼图：数据由父组件传入，便于复用 -->
<template>
  <div class="pie-wrap">
    <div ref="el" class="pie-root"></div>
    <div v-if="legendItems.length" class="legend-list" role="list" aria-label="政策类型标签">
      <span v-for="item in legendItems" :key="item.name" class="legend-chip" role="listitem">
        {{ item.name }}
      </span>
    </div>
  </div>
</template>

<script setup>
import * as echarts from 'echarts'
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

const props = defineProps({
  series: { type: Array, default: () => [] },
  /** 与政策目录主题词一致的一维列表，仅展示标签名（与饼图数据量口径一致，不含「其他」扇区） */
  topicLabels: { type: Array, default: () => [] },
})
const legendItems = computed(() => {
  const src =
    props.topicLabels && props.topicLabels.length
      ? props.topicLabels
      : (props.series || []).map((x) => x?.name)
  return src
    .map((x) => String(x ?? '').trim())
    .filter(Boolean)
    .map((name) => ({ name: name || '未命名类型' }))
})

const el = ref(null)
let chart
let ro
function onWinResize() {
  chart?.resize()
}

function render() {
  if (!chart) return
  if (!props.series?.length) {
    chart.clear()
    return
  }
  chart.setOption({
    color: [
      '#6a8fb5',
      '#86a8c8',
      '#6e8156',
      '#899a6f',
      '#8e76c3',
      '#a993d4',
      '#775da3',
      '#9178b6',
      '#5f6f71',
      '#7c8a8c',
      '#3a563c',
      '#4f6f52',
      '#6d6675',
      '#9e99a5',
    ],
    tooltip: { trigger: 'item', formatter: '{b}: {c}' },
    series: [
      {
        type: 'pie',
        radius: ['35%', '72%'],
        center: ['50%', '50%'],
        avoidLabelOverlap: true,
        minShowLabelAngle: 0,
        minAngle: 0,
        itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 1 },
        label: { fontSize: 11, color: '#111111', show: true, formatter: '{b}\n{c}' },
        data: props.series.map((x) => ({ name: x.name, value: x.value })),
      },
    ],
  })
}

onMounted(() => {
  nextTick(() => {
    if (!el.value) return
    chart = echarts.init(el.value)
    render()
    ro = new ResizeObserver(onWinResize)
    ro.observe(el.value)
    window.addEventListener('resize', onWinResize)
  })
})

onUnmounted(() => {
  ro?.disconnect()
  window.removeEventListener('resize', onWinResize)
  chart?.dispose()
  chart = null
})

watch(
  () => [props.series, props.topicLabels],
  () => render(),
  { deep: true },
)
</script>

<style scoped>
.pie-wrap {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.pie-root {
  width: 100%;
  height: 300px;
}
.legend-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: flex-start;
}
.legend-chip {
  display: inline-flex;
  align-items: center;
  border: 1px solid #E6CBA8;
  border-radius: 999px;
  background: #F9EAD2;
  color:rgb(122, 106, 86);
  font-size: 12px;
  line-height: 1.2;
  padding: 4px 10px;
}
</style>
