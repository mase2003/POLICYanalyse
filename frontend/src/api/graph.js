import axios from 'axios'
import { API_BASE_URL } from './base'

const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
})

export function fetchGraphStatus() {
  return client.get('/api/graph/status').then((r) => r.data)
}

export function queryGraph(query, limit = 300) {
  return client.post('/api/graph/query', { query, limit }).then((r) => r.data)
}

export function searchGraph(keyword, limit = 20) {
  return client
    .get('/api/graph/search', { params: { q: keyword, limit } })
    .then((r) => r.data)
}

export function expandNode(nodeId, depth = 1, limit = 100) {
  return client
    .get('/api/graph/expand', { params: { nodeId, depth, limit } })
    .then((r) => r.data)
}

export function fetchNodeDetail(nodeId) {
  return client.get('/api/graph/node-detail', { params: { nodeId } }).then((r) => r.data)
}

export function fetchPolicyDetail(nodeId) {
  return client.get('/api/graph/policy-detail', { params: { nodeId } }).then((r) => r.data)
}

/** 按标题/网址解析图库中政策节点 id（无则返回 nodeId: null） */
export function resolvePolicyNode(body) {
  return client.post('/api/graph/resolve-policy-node', body).then((r) => r.data)
}

export function fetchPolicyDirectionAnalysis(nodeId) {
  return client.get('/api/graph/direction-analysis', { params: { nodeId } }).then((r) => r.data)
}
