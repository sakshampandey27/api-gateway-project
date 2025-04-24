from fastapi import FastAPI
app = FastAPI()

@app.get("/")
def handle():
    return {"service": "service1", "message": "Hello from Service 1"}

@app.get("/health")
def health():
    return {"status": "healthy"}
