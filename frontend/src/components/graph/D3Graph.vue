<template>
  <div ref="wrapRef" class="graph-wrap">
    <svg ref="svgRef" class="graph-svg"></svg>
    <div
      v-if="bubbleVisible && policyMode"
      ref="bubbleRef"
      class="graph-bubble"
      :style="bubbleStyle"
      role="dialog"
      @click.stop
    >
      <button type="button" class="bubble-close" aria-label="关闭" @click="closeBubble">×</button>
      <div v-if="bubbleLoading" class="bubble-loading">加载详情…</div>
      <template v-else>
        <div class="bubble-labels">{{ bubbleLabelLine }}</div>
        <div class="bubble-body">
          <div v-for="row in bubbleRows" :key="row.key" class="bubble-row">
            <span class="bubble-k">{{ row.key }}</span>
            <span class="bubble-v">{{ row.value }}</span>
          </div>
        </div>
        <button type="button" class="bubble-expand" @click="emitExpand">扩展关联节点</button>
      </template>
    </div>
  </div>
</template>

<script setup>
import * as d3 from 'd3'
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { fetchNodeDetail } from '../../api/graph'

const props = defineProps({
  nodes: { type: Array, default: () => [] },
  edges: { type: Array, default: () => [] },
  /** 单条政策图谱：按标签着色、边上显示关系名、点击气泡展示属性 */
  policyMode: { type: Boolean, default: false },
})
const emit = defineEmits(['node-click', 'expand-node'])

const svgRef = ref(null)
const wrapRef = ref(null)
const bubbleRef = ref(null)

const bubbleVisible = ref(false)
const bubbleLoading = ref(false)
const bubblePos = ref({ x: 0, y: 0 })
const bubbleNode = ref(null)
const bubbleDetail = ref(null)

let simulation
let docClickHandler = null

const bubbleStyle = computed(() => {
  const pad = 12
  const w = 340
  const h = 280
  let left = bubblePos.value.x - w / 2
  let top = bubblePos.value.y - h - 24
  left = Math.max(pad, Math.min(left, window.innerWidth - w - pad))
  top = Math.max(pad, Math.min(top, window.innerHeight - h - pad))
  return {
    left: `${left}px`,
    top: `${top}px`,
    width: `${w}px`,
  }
})

const bubbleLabelLine = computed(() => {
  const n = bubbleNode.value
  if (!n) return ''
  return (n.labels || []).length ? (n.labels || []).join(' · ') : '节点'
})

const bubbleRows = computed(() => {
  const propsMap = bubbleDetail.value?.properties || {}
  const entries = Object.entries(propsMap)
  if (!entries.length) return [{ key: '（无属性）', value: '—' }]
  return entries.map(([key, value]) => ({
    key,
    value: value == null || value === '' ? '—' : String(value),
  }))
})

function nodeLabel(node) {
  return node?.properties?.name || node?.properties?.title || `Node ${node.id}`
}

function policyNodeCaption(node) {
  const lbs = node.labels || []
  const primary = lbs.length ? lbs.join(' · ') : '节点'
  const max = 22
  if (primary.length <= max) return primary
  return `${primary.slice(0, max)}…`
}

function measure() {
  const el = wrapRef.value
  if (!el) return { width: 800, height: 650 }
  const rect = el.getBoundingClientRect()
  const width = Math.max(rect.width || el.clientWidth, 400)
  const height = Math.max(rect.height || el.clientHeight, 400)
  return { width, height }
}

function buildColorScale(nodesIn) {
  const keys = [...new Set(nodesIn.flatMap((n) => n.labels || []))]
  if (!keys.length) keys.push('default')
  return d3.scaleOrdinal(d3.schemeTableau10).domain(keys)
}

function fillForNode(node, colorScale) {
  const lb = (node.labels && node.labels[0]) || 'default'
  return colorScale(lb)
}

function removeDocClick() {
  if (docClickHandler) {
    document.removeEventListener('click', docClickHandler, true)
    docClickHandler = null
  }
}

function closeBubble() {
  bubbleVisible.value = false
  bubbleNode.value = null
  bubbleDetail.value = null
  removeDocClick()
}

function attachDocClickClose() {
  removeDocClick()
  nextTick(() => {
    docClickHandler = (e) => {
      const el = bubbleRef.value
      if (el && el.contains(e.target)) return
      closeBubble()
    }
    document.addEventListener('click', docClickHandler, true)
  })
}

async function openPolicyBubble(event, d) {
  bubblePos.value = { x: event.clientX, y: event.clientY }
  bubbleVisible.value = true
  bubbleLoading.value = true
  bubbleNode.value = d
  bubbleDetail.value = null
  attachDocClickClose()
  try {
    bubbleDetail.value = await fetchNodeDetail(d.id)
  } catch {
    bubbleDetail.value = { properties: d.properties || {} }
  } finally {
    bubbleLoading.value = false
  }
}

function emitExpand() {
  if (bubbleNode.value) {
    emit('expand-node', bubbleNode.value)
  }
  closeBubble()
}

function onKeyEsc(e) {
  if (e.key === 'Escape' && bubbleVisible.value) closeBubble()
}

function draw() {
  const svgEl = svgRef.value
  if (!svgEl) return

  const { width, height } = measure()
  const svg = d3.select(svgEl)
  svg.selectAll('*').remove()
  svg.attr('viewBox', [0, 0, width, height])

  const g = svg.append('g')
  svg.call(
    d3.zoom().on('zoom', (event) => {
      g.attr('transform', event.transform)
    }),
  )

  const rawLinks = props.edges.map((edge) => ({
    ...edge,
    source: edge.source,
    target: edge.target,
  }))
  const nodes = props.nodes.map((node) => ({ ...node }))
  const colorScale = buildColorScale(nodes)

  const link = g
    .append('g')
    .attr('stroke', '#94a3b8')
    .attr('stroke-opacity', 0.85)
    .selectAll('line')
    .data(rawLinks)
    .join('line')
    .attr('stroke-width', props.policyMode ? 1.4 : 1.2)

  const edgeLabel = props.policyMode
    ? g
        .append('g')
        .attr('class', 'edge-labels')
        .selectAll('text')
        .data(rawLinks)
        .join('text')
        .attr('font-size', 10)
        .attr('fill', '#475569')
        .attr('text-anchor', 'middle')
        .attr('pointer-events', 'none')
        .text((d) => {
          const t = d.type || ''
          return t.length > 14 ? `${t.slice(0, 14)}…` : t
        })
    : null

  const node = g
    .append('g')
    .selectAll('circle')
    .data(nodes)
    .join('circle')
    .attr('r', props.policyMode ? 10 : 8)
    .attr('fill', (d) => (props.policyMode ? fillForNode(d, colorScale) : '#3b82f6'))
    .attr('stroke', '#fff')
    .attr('stroke-width', props.policyMode ? 1.5 : 0)
    .style('cursor', 'pointer')
    .on('click', function (event, d) {
      event.stopPropagation()
      if (props.policyMode) {
        openPolicyBubble(event, d)
      } else {
        emit('node-click', d)
      }
    })
    .call(
      d3
        .drag()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended),
    )

  const label = g
    .append('g')
    .selectAll('text')
    .data(nodes)
    .join('text')
    .text((d) => (props.policyMode ? policyNodeCaption(d) : nodeLabel(d)))
    .attr('font-size', props.policyMode ? 10 : 11)
    .attr('fill', props.policyMode ? '#334155' : '#111827')
    .attr('dx', props.policyMode ? 0 : 10)
    .attr('dy', props.policyMode ? 18 : 3)
    .attr('text-anchor', props.policyMode ? 'middle' : 'start')
    .attr('pointer-events', 'none')

  simulation = d3.forceSimulation(nodes)
  if (rawLinks.length > 0) {
    simulation.force(
      'link',
      d3
        .forceLink(rawLinks)
        .id((d) => d.id)
        .distance(props.policyMode ? 90 : 70),
    )
  }
  simulation
    .force('charge', d3.forceManyBody().strength(props.policyMode ? -220 : -180))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .on('tick', () => {
      link
        .attr('x1', (d) => d.source.x)
        .attr('y1', (d) => d.source.y)
        .attr('x2', (d) => d.target.x)
        .attr('y2', (d) => d.target.y)

      if (edgeLabel) {
        edgeLabel.attr('transform', (d) => {
          const sx = d.source.x
          const sy = d.source.y
          const tx = d.target.x
          const ty = d.target.y
          const mx = (sx + tx) / 2
          const my = (sy + ty) / 2
          const dx = tx - sx
          const dy = ty - sy
          const len = Math.sqrt(dx * dx + dy * dy) || 1
          const ox = (-dy / len) * 10
          const oy = (dx / len) * 10
          return `translate(${mx + ox},${my + oy})`
        })
      }

      node.attr('cx', (d) => d.x).attr('cy', (d) => d.y)
      label.attr('x', (d) => d.x).attr('y', (d) => d.y)
    })

  function dragstarted(event) {
    if (!event.active) simulation.alphaTarget(0.3).restart()
    event.subject.fx = event.subject.x
    event.subject.fy = event.subject.y
  }

  function dragged(event) {
    event.subject.fx = event.x
    event.subject.fy = event.y
  }

  function dragended(event) {
    if (!event.active) simulation.alphaTarget(0)
    event.subject.fx = null
    event.subject.fy = null
  }
}

let resizeObserver

onMounted(() => {
  draw()
  resizeObserver = new ResizeObserver(() => {
    if (simulation) simulation.stop()
    draw()
  })
  if (wrapRef.value) {
    resizeObserver.observe(wrapRef.value)
  }
  window.addEventListener('keydown', onKeyEsc)
})

onUnmounted(() => {
  removeDocClick()
  window.removeEventListener('keydown', onKeyEsc)
  if (resizeObserver && wrapRef.value) {
    resizeObserver.unobserve(wrapRef.value)
  }
  resizeObserver = null
  if (simulation) simulation.stop()
})

watch(
  () => [props.nodes, props.edges, props.policyMode],
  () => {
    if (simulation) simulation.stop()
    draw()
  },
  { deep: true },
)
</script>

<style scoped>
.graph-wrap {
  position: relative;
  width: 100%;
  min-height: 520px;
  height: 65vh;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
}
.graph-svg {
  width: 100%;
  height: 100%;
  display: block;
}
.graph-bubble {
  position: fixed;
  z-index: 50;
  max-height: min(70vh, 420px);
  overflow: auto;
  padding: 12px 14px 14px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  box-shadow: 0 10px 40px rgba(15, 23, 42, 0.15);
}
.bubble-close {
  position: absolute;
  top: 6px;
  right: 8px;
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  font-size: 20px;
  line-height: 1;
  color: #64748b;
  cursor: pointer;
  border-radius: 4px;
}
.bubble-close:hover {
  background: #f1f5f9;
  color: #0f172a;
}
.bubble-loading {
  padding: 12px 0;
  color: #64748b;
  font-size: 13px;
}
.bubble-labels {
  font-size: 12px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 10px;
  padding-right: 24px;
  word-break: break-word;
}
.bubble-body {
  font-size: 12px;
  line-height: 1.5;
  color: #334155;
}
.bubble-row {
  display: grid;
  grid-template-columns: 7.5em 1fr;
  gap: 8px;
  margin-bottom: 6px;
  align-items: start;
}
.bubble-k {
  color: #64748b;
  word-break: break-all;
}
.bubble-v {
  white-space: pre-wrap;
  word-break: break-word;
}
.bubble-expand {
  margin-top: 12px;
  padding: 6px 12px;
  font-size: 13px;
  color: #fff;
  background: #2563eb;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}
.bubble-expand:hover {
  background: #4B4453;
}
</style>
