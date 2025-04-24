from fastapi import FastAPI
app = FastAPI()

@app.get("/")
def handle():
    return {"service": "service2", "message": "Hello from Service 2"}

@app.get("/health")
def health():
    return {"status": "healthy"}
