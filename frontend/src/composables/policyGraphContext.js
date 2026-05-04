import { ref } from 'vue'

/** 知识图谱页要展示的节点 id（从首页/目录等点击政策时设置） */
export const graphFocusNodeId = ref(null)
export const graphFocusTitle = ref('')

/** MainLayout 监听此 key，切换到对应侧栏项后清空 */
export const sidebarNavigateKey = ref(null)

export function setGraphFocus(id, title) {
  graphFocusNodeId.value = id != null && id !== '' ? String(id) : null
  graphFocusTitle.value = title || ''
}

export function focusPolicyForGraph(id, title) {
  setGraphFocus(id, title)
  sidebarNavigateKey.value = 'graphPolicy'
}

/** 政策拆解页：待拆解的节点 id（由采集解析第五步等入口设置） */
export const policyDeconstructNodeId = ref(null)
export const policyDeconstructTitle = ref('')

export function focusPolicyDeconstruct(nodeId, title = '') {
  policyDeconstructNodeId.value = nodeId != null && nodeId !== '' ? String(nodeId) : null
  policyDeconstructTitle.value = title || ''
  sidebarNavigateKey.value = 'policyDeconstruct'
}
