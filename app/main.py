from fastapi import FastAPI
from app import routes

app = FastAPI(title="Raksha360 Backend API 🚀")

# include routes
app.include_router(routes.router)

@app.get("/")
def root():
    return {"message": "Welcome to Raksha360 API 🚀"}

@app.get("/health")
def health_check():
    return {"status": "ok"}
