import asyncio

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import List
from datetime import datetime

app = FastAPI(title="Online Resume Backend")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- Models ----------------
class RequestCreate(BaseModel):
    name: str
    email: EmailStr
    project_title: str
    description: str
    budget: int | None = None

class Request(RequestCreate):
    id: int
    created_at: datetime
    status: str = "pending"

# ---------------- Fake DB ----------------
requests_db: List[Request] = []

# ---------------- Auth ----------------
ADMIN_TOKEN = "admin123"

# توجه: Header با نام x_token تعریف شده تا در Swagger فیلد بسازه
def get_admin(x_token: str = Header(..., description="Admin token")):
    if x_token != ADMIN_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized"
        )

# ---------------- API ----------------
@app.post("/requests", response_model=Request)
def create_request(data: RequestCreate):
    req = Request(
        id=len(requests_db) + 1,
        created_at=datetime.utcnow(),
        **data.dict()
    )
    requests_db.append(req)
    return req

@app.get("/admin/requests", response_model=List[Request])
def list_requests(admin: bool = Depends(get_admin)):
    return requests_db

@app.delete("/admin/requests/{request_id}")
def delete_request(request_id: int, admin: bool = Depends(get_admin)):
    global requests_db
    requests_db = [r for r in requests_db if r.id != request_id]
    return {"message": "Deleted"}

@app.patch("/admin/requests/{request_id}/{status}")
def update_status(request_id: int, status: str, admin: bool = Depends(get_admin)):
    for r in requests_db:
        if r.id == request_id:
            r.status = status
            return r
    raise HTTPException(404, "Not found")

# ---------------- WebSocket ----------------
active_connections: set[WebSocket] = set()

async def broadcast_online_count():
    for ws in list(active_connections):
        try:
            await ws.send_json({"online": len(active_connections)})
        except:
            active_connections.remove(ws)

@app.websocket("/ws/online")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    active_connections.add(ws)

    await broadcast_online_count()

    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if ws in active_connections:
            active_connections.remove(ws)
            await broadcast_online_count()
