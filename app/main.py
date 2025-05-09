from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.api.routes import router as api_router
from app.db.database import init_db


@asynccontextmanager
async def lifespan(current_app: FastAPI):
    print("Application Lifespan: Startup sequence initiated...")
    try:
        init_db()
        print("Application Lifespan: Database initialized.")
    except Exception as e:
        print(f"Application Lifespan: Error during database initialization: {e}")

    yield

    print("Application Lifespan: Shutdown sequence initiated...")


app = FastAPI(
    title="CV Upload System",
    description="API for CV upload and job recommendations.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/")
async def root():
    return {"message": "CV Upload System API. Go to /docs for documentation."}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
