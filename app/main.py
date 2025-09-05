from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app import models
from app.database import engine
from app.routes import router  # assumes you fixed the router as described

# ✅ Create all tables in the database
models.Base.metadata.create_all(bind=engine)

# ✅ Initialize FastAPI app
app = FastAPI(
    title="Raksha360 Backend API 🚀",
    version="1.0.0",
    description="API for Doctor-Patient Appointment Booking and Management"
)

# ✅ CORS Middleware (for frontend like Vercel)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 🔐 Replace * with Vercel domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Include all routes from your unified router
app.include_router(router)

# ✅ Health check endpoint
@app.get("/health")
def health_check():
    return {"status": "ok"}

# ✅ Root endpoint
@app.get("/")
def root():
    return {"message": "Welcome to Raksha360 API 🚀"}
