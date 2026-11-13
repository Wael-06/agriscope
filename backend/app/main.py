# pyright: reportMissingImports=false
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import regions, recommendation, trends

app = FastAPI(title="AgriScope API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(regions.router)
app.include_router(recommendation.router)
app.include_router(trends.router)

@app.get("/")
def root():
    return {
        "service": "AgriScope API",
        "docs": "/docs",
        "endpoints": ["/health", "/regions", "/recommendation", "/trends"]
    }

@app.get("/health")
def health():
    return {"status": "ok"}
