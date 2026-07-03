"""Pydantic models for Roles, Users, and Auth."""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None

class RoleCreate(RoleBase):
    pass

class RoleResponse(RoleBase):
    id: int
    user_count: Optional[int] = 0
    created_at: datetime

class UserBase(BaseModel):
    name: str
    email: str
    role_id: int
    geo_scope: Optional[str] = None
    status: str = "Active"
    phone: Optional[str] = None

class UserCreate(UserBase):
    password: str
    username: Optional[str] = None

class UserUpdate(UserBase):
    password: Optional[str] = None
    username: Optional[str] = None

class UserResponse(UserBase):
    id: int
    username: Optional[str] = None
    role_name: Optional[str] = None
    last_login: Optional[datetime] = None
    created_at: datetime

class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    token: str
    user: UserResponse
