import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import nodes, k3s

app = FastAPI(title="homelab-dashboard", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://homelab.sacenpapier.org", "http://localhost:3000"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(nodes.router, prefix="/api")
app.include_router(k3s.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/pod")
async def pod_info():
    from fastapi.responses import JSONResponse
    return JSONResponse(
        content={
            "hostname": os.environ.get("HOSTNAME", ""),
            "node": os.environ.get("NODE_NAME", ""),
        },
        headers={"Cache-Control": "no-store", "Connection": "close"},
    )
