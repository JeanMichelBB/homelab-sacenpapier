import type { Node, K3sData, PodInfo } from '../types/index'

const BASE = import.meta.env.VITE_API_URL ?? '/api'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`${path} ${res.status}`)
  return res.json()
}

export const api = {
  nodes: () => get<Node[]>('/nodes'),
  k3s: () => get<K3sData>('/k3s'),
  pod: () => fetch(`/pod.json?t=${Date.now()}`).then(r => r.ok ? r.json() : Promise.reject()) as Promise<PodInfo>,
}
