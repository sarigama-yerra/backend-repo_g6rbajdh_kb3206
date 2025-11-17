import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from bson import ObjectId
from datetime import datetime

from database import db, create_document, get_documents

app = FastAPI(title="FutureMe API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Utils
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

def serialize_doc(doc: dict):
    if not doc:
        return doc
    doc["id"] = str(doc.pop("_id")) if doc.get("_id") else None
    # Convert datetimes to isoformat
    for k, v in list(doc.items()):
        if hasattr(v, "isoformat"):
            doc[k] = v.isoformat()
    return doc


# ===== Auth (MVP mock) =====
class RegisterRequest(BaseModel):
    email: str
    password: str
    name: Optional[str] = None

class LoginRequest(BaseModel):
    email: str
    password: str

class GoogleAuthRequest(BaseModel):
    id_token: str

@app.post("/api/auth/register")
def register(req: RegisterRequest):
    user_col = db["user"]
    existing = user_col.find_one({"email": req.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = {
        "email": req.email,
        "name": req.name or req.email.split("@")[0],
        # NOTE: For MVP we store plaintext; in real app hash this
        "password_hash": req.password,
        "auth_provider": "password",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    inserted_id = user_col.insert_one(user).inserted_id
    return {"token": str(inserted_id), "user": {"id": str(inserted_id), "email": user["email"], "name": user["name"]}}

@app.post("/api/auth/login")
def login(req: LoginRequest):
    user = db["user"].find_one({"email": req.email, "password_hash": req.password})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"token": str(user["_id"]), "user": {"id": str(user["_id"]), "email": user["email"], "name": user.get("name")}}

@app.post("/api/auth/google")
def google_auth(req: GoogleAuthRequest):
    # Mock verification - accept any id_token and derive email
    email = f"{req.id_token[:6]}@googleuser.dev"
    user_col = db["user"]
    user = user_col.find_one({"email": email})
    if not user:
        user = {
            "email": email,
            "name": "Google User",
            "auth_provider": "google",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        user["_id"] = user_col.insert_one(user).inserted_id
    return {"token": str(user["_id"]), "user": {"id": str(user["_id"]), "email": user["email"], "name": user.get("name")}}


# ===== Vision =====
class VisionRequest(BaseModel):
    user_id: str
    career: str
    lifestyle: str
    timeline: str

@app.post("/api/vision")
def create_vision(req: VisionRequest):
    # Mock AI summarization
    summary = (
        f"In {req.timeline}, you see yourself advancing in {req.career}, "
        f"living a {req.lifestyle} lifestyle. You balance growth and wellbeing with clear, achievable milestones."
    )
    milestones = [
        f"Define a 90-day plan toward {req.career}",
        "Establish weekly reflection ritual",
        "Ship one portfolio-worthy project",
        "Expand your network with 5 meaningful connections",
    ]
    emotional = "You feel confident, focused, and quietly proud of your momentum."
    vision_doc = {
        "user_id": req.user_id,
        "career": req.career,
        "lifestyle": req.lifestyle,
        "timeline": req.timeline,
        "summary": summary,
        "milestones": milestones,
        "emotional_impact": emotional,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    inserted_id = db["vision"].insert_one(vision_doc).inserted_id
    vision_doc["_id"] = inserted_id
    return serialize_doc(vision_doc)

@app.get("/api/vision")
def get_latest_vision(user_id: str):
    vision = db["vision"].find({"user_id": user_id}).sort("created_at", -1).limit(1)
    docs = list(vision)
    if not docs:
        return {}
    return serialize_doc(docs[0])


# ===== Goals CRUD =====
class GoalCreate(BaseModel):
    user_id: str
    title: str
    description: Optional[str] = None
    target_date: Optional[str] = None
    progress: int = Field(0, ge=0, le=100)
    category: Optional[str] = None

class GoalUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    target_date: Optional[str] = None
    progress: Optional[int] = Field(None, ge=0, le=100)
    category: Optional[str] = None

@app.get("/api/goals")
def list_goals(user_id: str):
    docs = db["goal"].find({"user_id": user_id}).sort("created_at", -1)
    return [serialize_doc(d) for d in docs]

@app.post("/api/goals")
def create_goal(g: GoalCreate):
    doc = g.model_dump()
    doc["created_at"] = datetime.utcnow()
    doc["updated_at"] = datetime.utcnow()
    inserted = db["goal"].insert_one(doc).inserted_id
    doc["_id"] = inserted
    return serialize_doc(doc)

@app.put("/api/goals/{goal_id}")
def update_goal(goal_id: str, g: GoalUpdate):
    updates = {k: v for k, v in g.model_dump().items() if v is not None}
    updates["updated_at"] = datetime.utcnow()
    res = db["goal"].find_one_and_update({"_id": ObjectId(goal_id)}, {"$set": updates}, return_document=True)
    if not res:
        raise HTTPException(status_code=404, detail="Goal not found")
    return serialize_doc(res)

@app.delete("/api/goals/{goal_id}")
def delete_goal(goal_id: str):
    res = db["goal"].delete_one({"_id": ObjectId(goal_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Goal not found")
    return {"ok": True}


# ===== Chat (mock) =====
class ChatRequest(BaseModel):
    user_id: str
    message: str

@app.post("/api/chat")
def chat(req: ChatRequest):
    # Simple reflective response
    reply = (
        "I hear you. Given your current goals, a tiny action today could be to spend "
        "15 minutes outlining the next step. What would make that easy right now?"
    )
    return {"reply": reply}


@app.get("/")
def read_root():
    return {"message": "FutureMe API is running"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    import os as _os
    response["database_url"] = "✅ Set" if _os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if _os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
