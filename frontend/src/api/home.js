import axios from 'axios'
import { API_BASE_URL } from './base'

const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
})

export function fetchHomeDashboard() {
  return client.get('/api/home/dashboard').then((r) => r.data)
}

export function reportSearchHit(nodeId) {
  return client.post('/api/home/search-hit', { nodeId }).then((r) => r.data)
}
