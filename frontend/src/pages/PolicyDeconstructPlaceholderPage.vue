<template>
  <section class="panel">
    <h3 class="page-title">{{ title }}</h3>
    <p class="muted">
      在首页、政策目录或搜索结果中选择一条政策后，将自动带入下方；也可从「政策采集解析」等入口跳转，点击按钮将拆解此政策。
    </p>

    <div v-if="!policyDeconstructNodeId" class="warn-box">
      尚未选择政策。请先在其它页面选择一条政策，或从采集解析流程跳转。
    </div>

    <div v-else class="card">
      <p class="policy-line">
        <span class="label">当前政策</span>
        <strong>{{ policyDeconstructTitle || '（无标题）' }}</strong>
      </p>
      <p class="meta">节点 id：<span class="mono">{{ policyDeconstructNodeId }}</span></p>
      <div class="card-actions">
        <a-button type="primary" :loading="loading" :disabled="loading" @click="runDeconstruct">
          {{ loading ? '拆解中（可能需数分钟）…' : '开始拆解' }}
        </a-button>
        <a-button :disabled="!resultRow" @click="exportCsv">导出 policyexplain.csv（本行）</a-button>
      </div>
    </div>

    <div v-if="errorMsg" class="alert err">{{ errorMsg }}</div>
    <div v-if="rateHint" class="alert hint">{{ rateHint }}</div>

    <div v-if="resultRaw" class="result-block">
      <div class="result-head">
        <h4>拆解结果</h4>

      </div>
      <pre class="result-pre">{{ resultRaw }}</pre>
    </div>
  </section>
</template>

<script setup>
import { ref, watch } from 'vue'
import { deconstructPolicy } from '../api/policyExplain'
import { downloadPolicyExplainCsv } from '../constants/policyExplainCsv'
import {
  policyDeconstructNodeId,
  policyDeconstructTitle,
} from '../composables/policyGraphContext'

defineProps({
  title: { type: String, default: '政策拆解' },
})

const loading = ref(false)
const errorMsg = ref('')
const rateHint = ref('')
const resultRaw = ref('')
/** 与 policyexplain.csv 列一致的结构化行（接口返回 data.row） */
const resultRow = ref(null)

watch(policyDeconstructNodeId, () => {
  resultRaw.value = ''
  resultRow.value = null
  errorMsg.value = ''
  rateHint.value = ''
})

function apiErrorMessage(err) {
  const d = err.response?.data
  if (typeof d === 'string') return d
  if (d?.error) return d.error
  return err.message || '请求失败'
}

function exportCsv() {
  if (!resultRow.value || typeof resultRow.value !== 'object') return
  downloadPolicyExplainCsv('policyexplain.csv', [resultRow.value])
}

async function runDeconstruct() {
  const id = policyDeconstructNodeId.value
  if (!id) return
  errorMsg.value = ''
  rateHint.value = ''
  resultRaw.value = ''
  resultRow.value = null
  loading.value = true
  try {
    const data = await deconstructPolicy(id)
    resultRaw.value = data.rawText || ''
    resultRow.value = data.row && typeof data.row === 'object' ? { ...data.row } : null
    const lim = data.dailyLimit
    const used = data.usedToday
    if (lim != null && used != null) {
      rateHint.value = `今日已用 ${used} / ${lim} 次（非本机 IP 限流）。`
    }
  } catch (err) {
    errorMsg.value = apiErrorMessage(err)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.panel {
  max-width: 880px;
  margin: 0 auto;
}
.page-title {
  margin: 0 0 12px;
  font-size: 18px;
  color: #111827;
}
.muted {
  color: #6b7280;
  font-size: 14px;
  line-height: 1.6;
}
.warn-box {
  margin-top: 16px;
  padding: 12px 14px;
  background: #fffbeb;
  border: 1px solid #fcd34d;
  border-radius: 8px;
  color: #92400e;
  font-size: 14px;
}
.card {
  margin-top: 20px;
  padding: 16px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}
.policy-line {
  margin: 0 0 8px;
  font-size: 14px;
  line-height: 1.5;
}
.policy-line .label {
  color: #6b7280;
  margin-right: 8px;
}
.meta {
  margin: 0 0 12px;
  font-size: 13px;
  color: #64748b;
}
.card-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}
.result-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}
.mono {
  font-family: ui-monospace, monospace;
  word-break: break-all;
}
.alert {
  margin-top: 16px;
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 14px;
}
.alert.err {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #b91c1c;
}
.alert.hint {
  background: #F9EAD2;
  border: 1px solid #E6CBA8;
  color: #1e40af;
}
.result-block {
  margin-top: 20px;
}
.result-head h4 {
  margin: 0;
  font-size: 15px;
  color: #111827;
}
.result-pre {
  margin: 0;
  padding: 14px;
  background: rgb(239, 232, 230);
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 70vh;
  overflow: auto;
}
</style>
