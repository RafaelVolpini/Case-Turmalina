from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routes import router

app = FastAPI(title="Turmalina Café -- Dashboard de Análise de Lojas")

app.mount("/styles", StaticFiles(directory="styles"), name="styles")
app.include_router(router)
