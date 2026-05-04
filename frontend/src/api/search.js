import axios from 'axios'
import { API_BASE_URL } from './base'

const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
})

export function searchPolicies(q, limit = 30) {
  return client
    .get('/api/search/policies', { params: { q, limit } })
    .then((r) => r.data)
}
