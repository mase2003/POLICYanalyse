const rawBase = import.meta.env.VITE_API_BASE_URL

// Use same-origin API by default for production reverse proxy setups.
export const API_BASE_URL = rawBase == null ? '' : String(rawBase).trim()
