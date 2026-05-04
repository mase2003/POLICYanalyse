import axios from 'axios'
import { API_BASE_URL } from './base'

const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 300000,
})

export function deconstructPolicy(nodeId) {
  return client.post('/api/policy-explain/deconstruct', { nodeId }).then((r) => r.data)
}
