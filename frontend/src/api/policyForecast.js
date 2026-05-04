import axios from 'axios'
import { API_BASE_URL } from './base'

const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000,
})

export function fetchFifteenFiveBundle() {
  return client.get('/api/policy-forecast/fifteen-five').then((r) => r.data)
}

export function fetchParty20Bundle() {
  return client.get('/api/policy-forecast/party-20').then((r) => r.data)
}

export function postCrawlerParse(body) {
  return client.post('/api/policy-forecast/crawler-parse', body).then((r) => r.data)
}

/** 返回 axios 响应（blob），便于读取 Content-Disposition 文件名 */
export function postCrawlerParseExport(body) {
  return client.post('/api/policy-forecast/crawler-parse/export', body, { responseType: 'blob' })
}
