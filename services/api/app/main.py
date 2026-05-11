from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.api.app.routers.designs import router as designs_router


app = FastAPI(title="AeroSpec Agent API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(designs_router)


@app.get("/health")
def health():
    return {"status": "ok"}
