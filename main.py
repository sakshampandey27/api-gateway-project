from fastapi import FastAPI, Request, HTTPException, Depends
import time, jwt, asyncio, httpx
from typing import Dict, List
from prometheus_client import Counter, generate_latest
import structlog
from itertools import cycle


SECRET_KEY = "jobs2025"
RATE_LIMIT = 5          # tokens
REFILL_INTERVAL = 60    # seconds
ROUTES = ["http://localhost:8001", "http://localhost:8002"]

rate_limit_store = {} # in-memory store for rate limiting
request_count = Counter("gateway_requests_total", "Requests routed", ["route"])
healthy_routes = ROUTES.copy()
routes_cycle = cycle(healthy_routes)


logger = structlog.get_logger()
app = FastAPI()
client = httpx.AsyncClient()


def verify_jwt(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")

    token = auth_header.split(" ")[1]    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def allow_request(user_id, rate=RATE_LIMIT, per=REFILL_INTERVAL):
    now = time.time()
    user_data = rate_limit_store.get(user_id, {"tokens": RATE_LIMIT, "last": now})

    elapsed = now - user_data["last"]
    refill = (elapsed / REFILL_INTERVAL) * RATE_LIMIT
    user_data["tokens"] = min(RATE_LIMIT, user_data["tokens"] + refill)
    user_data["last"] = now

    if user_data["tokens"] >= 1:
        user_data["tokens"] -= 1
        rate_limit_store[user_id] = user_data
        return True
    else:
        return False

# === Health Check Task ===
async def health_check():
    while True:
        global healthy_routes, routes_cycle
        updated = []
        for route in ROUTES:
            try:
                r = await client.get(f"{route}/health", timeout=1)
                if r.status_code == 200:
                    updated.append(route)
            except:
                pass
        healthy_routes = updated or []
        routes_cycle = cycle(healthy_routes)
        await asyncio.sleep(15)  # Check every 15 seconds


# === Startup ===
@app.on_event("startup")
async def on_startup():
    asyncio.create_task(health_check())


# === Logging and Counting ===
@app.middleware("http")
async def log_requests(request: Request, call_next):
    response = await call_next(request)
    logger.info(
        "request_log",
        path=request.url.path,
        method=request.method,
        status=response.status_code
    )
    return response

@app.middleware("http")
async def count_requests(request: Request, call_next):
    request_count.labels(route=request.url.path).inc()
    return await call_next(request)



# === Gateway Endpoint with Load Balancing ===
@app.get("/gateway")
async def gateway(request: Request, user=Depends(verify_jwt)):
    user_id = user.get("sub")
    if not allow_request(user_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    for _ in range(len(healthy_routes)):
        route = next(routes_cycle)
        try:
            response = await client.get(f"{route}/", timeout=2)
            request_count.labels(route=route).inc()
            return {"route": route, "response": response.json(), "user": user_id}
        except Exception:
            continue

    raise HTTPException(status_code=503, detail="No healthy routes available")

@app.get("/health")
def read_root():
    return {"message": "API Gateway is running and healthy!"}


# @app.get("/service1")
# async def service1(request: Request, user=Depends(verify_jwt)):
#     user_id = user.get("sub")
#     if not allow_request(user_id):
#         raise HTTPException(status_code=429, detail="Rate limit exceeded")
#     return {"message": f"Hello from service 1, {user_id}!"}

# @app.get("/service2")
# async def service2(request: Request, user=Depends(verify_jwt)):
#     user_id = user.get("sub")
#     if not allow_request(user_id):
#         raise HTTPException(status_code=429, detail="Rate limit exceeded")
#     return {"message": f"Hello from service 2, {user_id}!"}



@app.get("/metrics")
def metrics():
    return generate_latest()
