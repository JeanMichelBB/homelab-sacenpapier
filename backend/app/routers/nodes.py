import asyncio
import logging
import httpx
from fastapi import APIRouter
from ..cache import cache_get_stale, cache_set_stale
from ..clients import prometheus
from ..config import settings

router = APIRouter()
_KEY = "nodes"
_TTL = 15
_GLANCES_TIMEOUT = 2
_TRUENAS_TIMEOUT = 3

log = logging.getLogger(__name__)
_refresh_lock = asyncio.Lock()


async def _glances_node(name: str, url: str, role: str, tailscale_ip: str) -> dict:
    base = {
        "name": name, "role": role, "tailscale_ip": tailscale_ip,
        "online": False, "cpu_percent": None, "ram_percent": None, "uptime_seconds": None,
    }
    try:
        async with httpx.AsyncClient(timeout=_GLANCES_TIMEOUT) as client:
            cpu_r, mem_r, uptime_r = await asyncio.gather(
                client.get(f"{url}/api/4/cpu/total"),
                client.get(f"{url}/api/4/mem/percent"),
                client.get(f"{url}/api/4/uptime"),
            )
            base["online"] = True
            cpu_val = cpu_r.json() if cpu_r.status_code == 200 else None
            mem_val = mem_r.json() if mem_r.status_code == 200 else None
            base["cpu_percent"] = round(float(cpu_val["total"]), 1) if isinstance(cpu_val, dict) else (round(float(cpu_val), 1) if cpu_val is not None else None)
            base["ram_percent"] = round(float(mem_val["percent"]), 1) if isinstance(mem_val, dict) else (round(float(mem_val), 1) if mem_val is not None else None)
            raw_uptime = uptime_r.json() if uptime_r.status_code == 200 else None
            if isinstance(raw_uptime, (int, float)):
                base["uptime_seconds"] = raw_uptime
    except Exception:
        pass
    return base


async def _prometheus_node(name: str, role: str, tailscale_ip: str, instance: str) -> dict:
    base = {
        "name": name, "role": role, "tailscale_ip": tailscale_ip,
        "online": False, "cpu_percent": None, "ram_percent": None, "uptime_seconds": None,
    }
    try:
        cpu_res = await prometheus.query(f'100 - avg by(instance)(rate(node_cpu_seconds_total{{mode="idle",instance="{instance}"}}[2m])) * 100')
        mem_res = await prometheus.query(f'(1 - node_memory_MemAvailable_bytes{{instance="{instance}"}} / node_memory_MemTotal_bytes{{instance="{instance}"}}) * 100')
        uptime_res = await prometheus.query(f'node_time_seconds{{instance="{instance}"}} - node_boot_time_seconds{{instance="{instance}"}}')
        if cpu_res:
            base["online"] = True
            base["cpu_percent"] = round(float(cpu_res[0]["value"][1]), 1)
        if mem_res:
            base["ram_percent"] = round(float(mem_res[0]["value"][1]), 1)
        if uptime_res:
            base["uptime_seconds"] = int(float(uptime_res[0]["value"][1]))
    except Exception:
        pass
    return base


async def _truenas_node() -> dict:
    ip = settings.tailscale_ip_truenas
    base = {
        "name": "tstruenas", "role": "NAS — TrueNAS Scale, ZFS mirror",
        "tailscale_ip": ip,
        "online": False, "cpu_percent": None, "ram_percent": None, "uptime_seconds": None,
    }
    try:
        import httpx as hx
        async with hx.AsyncClient(timeout=_TRUENAS_TIMEOUT, verify=False) as client:
            r = await client.get(
                f"{settings.truenas_url}/api/v2.0/system/info",
                headers={"Authorization": f"Bearer {settings.truenas_api_key}"},
            )
            if r.status_code == 200:
                data = r.json()
                base["online"] = True
                base["uptime_seconds"] = data.get("uptime_seconds")
    except Exception:
        pass
    return base


async def _fetch_all() -> list:
    ip_e = settings.tailscale_ip_elitedesk
    ip_pi = settings.tailscale_ip_tspi
    ip_win = settings.tailscale_ip_windows
    ip_o1 = settings.tailscale_ip_oci1
    ip_o2 = settings.tailscale_ip_oci2

    return await asyncio.gather(
        _glances_node("tselitedesk", settings.glances_elitedesk_url,
                      "Main server — media, k3s control plane, gpu-proxy", ip_e),
        _glances_node("tspi", settings.glances_tspi_url,
                      "Monitoring — Prometheus, Grafana", ip_pi),
        _glances_node("tswindows11", settings.glances_win_url, "Gaming PC — Ollama RTX 5070", ip_win),
        _truenas_node(),
        _prometheus_node("oci-node-1", "k3s worker (OCI free tier)", ip_o1, f"{ip_o1}:9100"),
        _prometheus_node("oci-node-2", "k3s worker (OCI free tier)", ip_o2, f"{ip_o2}:9100"),
    )


async def _refresh_in_background() -> None:
    if _refresh_lock.locked():
        return
    async with _refresh_lock:
        try:
            results = await _fetch_all()
            await cache_set_stale(_KEY, results)
        except Exception:
            log.exception("background nodes refresh failed")


@router.get("/nodes")
async def get_nodes():
    cached, is_fresh = await cache_get_stale(_KEY, _TTL)

    if cached is not None:
        if not is_fresh:
            asyncio.create_task(_refresh_in_background())
        return cached

    # Cold start only (no cached value yet) — nothing to serve, so wait for the real fetch.
    results = await _fetch_all()
    await cache_set_stale(_KEY, results)
    return results
