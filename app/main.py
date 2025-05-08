from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager  # 1. Import asynccontextmanager

# --- Application specific imports ---
from app.api.routes import router as api_router
from app.db.database import init_db


# 2. Define the lifespan context manager
@asynccontextmanager
async def lifespan(current_app: FastAPI):
    # Code to run on startup
    print("Application Lifespan: Startup sequence initiated...")
    try:
        init_db()  # Call your database initialization function
        print("Application Lifespan: Database initialized.")
    except Exception as e:
        print(f"Application Lifespan: Error during database initialization: {e}")
        # Depending on the severity, you might want to raise the exception
        # to prevent the app from starting if DB init fails.
        # raise e

    yield  # The application runs while yielded

    # Code to run on shutdown (optional)
    print("Application Lifespan: Shutdown sequence initiated...")
    # Add any cleanup logic here, e.g., closing connection pools if you manage them manually


# 3. Create FastAPI app instance and pass the lifespan manager
app = FastAPI(
    title="CV Upload System",
    description="API for CV upload and job recommendations.",  # Added description
    version="1.0.0",  # Added version
    lifespan=lifespan  # Pass the lifespan function here
)

# --- Remove the old @app.on_event decorator and function ---
# @app.on_event("startup") # REMOVE THIS
# async def startup_event(): # REMOVE THIS FUNCTION
#     # Initialize database on startup # REMOVE THIS
#     init_db() # REMOVE THIS

# Add CORS middleware (remains the same)
app.add_middleware(
    CORSMiddleware,
    # Adjust allow_origins as needed for production
    allow_origins=["http://localhost:5173"],  # Allow your frontend origin
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Include API routes (remains the same)
app.include_router(api_router)


# Root endpoint (remains the same)
@app.get("/")
async def root():
    return {"message": "CV Upload System API. Go to /docs for documentation."}


# uvicorn run command (remains the same for running directly)
if __name__ == "__main__":
    import uvicorn

    # Ensure the path 'app.main:app' matches your file structure and app instance name
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
