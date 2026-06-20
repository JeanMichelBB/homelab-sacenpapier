export interface Node {
  name: string
  role: string
  tailscale_ip: string
  online: boolean
  cpu_percent: number | null
  ram_percent: number | null
  uptime_seconds: number | null
}

export interface K3sNode {
  name: string
  status: string
  role: string
}

export interface K3sData {
  nodes: K3sNode[]
  pods: { total: number; running: number; pending: number; failed: number }
}

export interface PodInfo {
  hostname: string
  node: string
}
