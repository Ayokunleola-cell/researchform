# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from api.routers import auth, surveys, responses, analysis, export, users
from config import settings

app = FastAPI(title="ResearchForm API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(auth.router,      prefix="/auth",     tags=["Auth"])
app.include_router(users.router,     prefix="/users",    tags=["Users"])
app.include_router(surveys.router,   prefix="/surveys",  tags=["Surveys"])
app.include_router(responses.router, prefix="/public",   tags=["Public"])
app.include_router(analysis.router,  prefix="/analysis", tags=["Analysis"])
app.include_router(export.router,    prefix="/export",   tags=["Export"])

for d in ["storage/charts","storage/reports","storage/dataframes"]:
    os.makedirs(d, exist_ok=True)
app.mount("/storage", StaticFiles(directory="storage"), name="storage")

@app.get("/health")
def health(): return {"status": "ok", "version": "1.0.0"}
