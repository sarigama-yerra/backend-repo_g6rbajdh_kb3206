"""
Database Schemas for FutureMe

Each Pydantic model represents a collection in MongoDB. The collection name is the lowercase
of the class name (e.g., Goal -> "goal").
"""
from typing import Optional, List
from pydantic import BaseModel, Field

class User(BaseModel):
    email: str = Field(..., description="Email address")
    name: Optional[str] = Field(None, description="Full name")
    password_hash: Optional[str] = Field(None, description="Password hash for email/password auth")
    auth_provider: str = Field("password", description="Auth provider: password|google")

class Vision(BaseModel):
    user_id: str = Field(..., description="Owner user id")
    career: str
    lifestyle: str
    timeline: str
    summary: Optional[str] = None
    milestones: Optional[List[str]] = None
    emotional_impact: Optional[str] = None

class Goal(BaseModel):
    user_id: str = Field(..., description="Owner user id")
    title: str
    description: Optional[str] = None
    target_date: Optional[str] = None
    progress: int = Field(0, ge=0, le=100)
    category: Optional[str] = None
