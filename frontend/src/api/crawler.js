import axios from 'axios'
import { API_BASE_URL } from './base'

const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
})
let contentManagePassword = ''

export function setPolicyContentManagePassword(password) {
  contentManagePassword = String(password || '').trim()
}

function contentHeaders() {
  return contentManagePassword ? { 'X-Content-Manage-Password': contentManagePassword } : {}
}

export function fetchLatestCrawlerTask() {
  return client.get('/api/crawler/latest-task').then((r) => r.data)
}

export function startCrawlerTask(payload) {
  return client.post('/api/crawler/start', payload).then((r) => r.data)
}

export function fetchCrawlerStatus(taskId) {
  return client.get('/api/crawler/status', { params: { taskId } }).then((r) => r.data)
}

export function exportCrawlerCsv(taskId) {
  return client.post('/api/crawler/export', { taskId }).then((r) => r.data)
}

export function exportCrawlerXlsx(taskId, rowIds) {
  return client.post('/api/crawler/export-xlsx', { taskId, rowIds }).then((r) => r.data)
}

export function importCrawlerRows(taskId, rowIds) {
  return client.post('/api/crawler/import-db', { taskId, rowIds }).then((r) => r.data)
}

export function fetchPolicyContentList(params) {
  return client.get('/api/crawler/content/list', { params, headers: contentHeaders() }).then((r) => r.data)
}

export function fetchPolicyContentDetail(nodeId) {
  return client.get('/api/crawler/content/detail', { params: { nodeId }, headers: contentHeaders() }).then((r) => r.data)
}

export function updatePolicyContentFields(nodeId, updates) {
  return client.post('/api/crawler/content/update-fields', { nodeId, updates }, { headers: contentHeaders() }).then((r) => r.data)
}

export function deletePolicyContentField(nodeId, field) {
  return client.post('/api/crawler/content/delete-field', { nodeId, field }, { headers: contentHeaders() }).then((r) => r.data)
}

export function deletePolicyContentRelation(relId) {
  return client.post('/api/crawler/content/delete-relation', { relId }, { headers: contentHeaders() }).then((r) => r.data)
}

export function deletePolicyContentRelations(relIds) {
  return client.post('/api/crawler/content/delete-relations', { relIds }, { headers: contentHeaders() }).then((r) => r.data)
}

export function deletePolicyContentNode(nodeId) {
  return client.post('/api/crawler/content/delete-node', { nodeId }, { headers: contentHeaders() }).then((r) => r.data)
}

export function unlockPolicyContentManage(password) {
  return client.post('/api/crawler/content/unlock', { password }).then((r) => r.data)
}
