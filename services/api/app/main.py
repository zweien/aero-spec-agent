import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.api.app.routers.designs import router as designs_router


def _local_web_origins() -> list[str]:
    web_port = os.getenv("WEB_PORT", "3900")
    return [
        f"http://localhost:{web_port}",
        f"http://127.0.0.1:{web_port}",
    ]


app = FastAPI(title="AeroSpec Agent API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_local_web_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(designs_router)


@app.get("/health")
def health():
    return {"status": "ok"}
