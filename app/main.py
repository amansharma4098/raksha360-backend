from fastapi import FastAPI
from app import models, routes
from app.database import engine
from fastapi.middleware.cors import CORSMiddleware

# Create DB tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Raksha360 Backend API 🚀")

# ✅ Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restrict to your Vercel domains for security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# include routes
app.include_router(routes.router)

@app.get("/")
def root():
    return {"message": "Welcome to Raksha360 API 🚀"}

@app.get("/health")
def health_check():
    return {"status": "ok"}
