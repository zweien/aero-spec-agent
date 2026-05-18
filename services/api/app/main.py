import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.api.app.routers.chat import router as chat_router
from services.api.app.routers.chat import set_job_runner as set_chat_job_runner
from services.api.app.routers.design_controller import router as design_controller_router
from services.api.app.routers.designs import router as designs_router
from services.api.app.routers.designs import runner as designs_runner


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
app.include_router(chat_router)
app.include_router(design_controller_router)

set_chat_job_runner(designs_runner)


@app.get("/health")
def health():
    return {"status": "ok"}
