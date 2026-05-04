import axios from 'axios'
import { API_BASE_URL } from './base'

const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
})

export function fetchOfficialReadFilters() {
  return client.get('/api/official-read/filters').then((r) => r.data)
}

export function fetchOfficialReadList(params) {
  return client.get('/api/official-read/list', { params }).then((r) => r.data)
}

export function fetchOfficialReadDetail(id) {
  return client.get('/api/official-read/detail', { params: { id } }).then((r) => r.data)
}

export function fetchOfficialReadDirectionAnalysis(id) {
  return client.get('/api/official-read/direction-analysis', { params: { id } }).then((r) => r.data)
}
