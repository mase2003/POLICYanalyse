import axios from 'axios'
import { API_BASE_URL } from './base'

const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
})

export function fetchCatalogFilters() {
  return client.get('/api/catalog/filters').then((r) => r.data)
}

export function fetchCatalogPolicies(params) {
  return client.get('/api/catalog/policies', { params }).then((r) => r.data)
}

export function fetchTopicChildren(topic) {
  return client
    .get('/api/catalog/topic-children', { params: { topic } })
    .then((r) => r.data)
}
