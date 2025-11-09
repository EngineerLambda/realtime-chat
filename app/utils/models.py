from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from bson import ObjectId


class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)


# --- Auth Payloads ---

class SignupPayload(BaseModel):
    username: str
    email: EmailStr
    password: str

class LoginPayload(BaseModel):
    email: EmailStr
    password: str

class ForgotPasswordPayload(BaseModel):
    email: EmailStr

class ResendOTPPayload(BaseModel):
    email: EmailStr

class ResetPasswordPayload(BaseModel):
    email: EmailStr
    otp_code: str
    new_password: str
    confirm_new_password: str

class RefreshPayload(BaseModel):
    refresh_token: str

class LogoutPayload(BaseModel):
    refresh_token: Optional[str] = None


# --- Chat Payloads ---

class CreateGroupPayload(BaseModel):
    name: str
    members: List[str]

class JoinGroupPayload(BaseModel):
    name: str

class AiChatPayload(BaseModel):
    content: str


# --- Database Models ---

class UserBase(BaseModel):
    username: str
    email: EmailStr

class UserInDB(UserBase):
    password_hash: str

class UserOut(UserBase):
    id: PyObjectId = Field(alias="_id")
    created_at: datetime

    class Config:
        json_encoders = {ObjectId: str}
        allow_population_by_field_name = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: Optional[str]


class Session(BaseModel):
    id: PyObjectId = Field(alias="_id")
    user_id: PyObjectId
    refresh_token: str
    created_at: datetime
    expires_at: datetime


class Group(BaseModel):
    id: PyObjectId = Field(alias="_id")
    name: str
    members: List[PyObjectId] = []
    created_at: datetime


class Message(BaseModel):
    id: PyObjectId = Field(alias="_id")
    chat_id: str
    sender_id: PyObjectId
    content: str
    created_at: datetime
    is_group: bool = False

    class Config:
        json_encoders = {ObjectId: str}
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)


class UserIn(BaseModel):
    username: str
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: PyObjectId = Field(alias="_id")
    username: str
    email: EmailStr
    created_at: datetime

    class Config:
        json_encoders = {ObjectId: str}
        allow_population_by_field_name = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: Optional[str]


class Session(BaseModel):
    id: PyObjectId = Field(alias="_id")
    user_id: PyObjectId
    refresh_token: str
    created_at: datetime
    expires_at: datetime


class Group(BaseModel):
    id: PyObjectId = Field(alias="_id")
    name: str
    members: List[PyObjectId] = []
    created_at: datetime


class Message(BaseModel):
    id: PyObjectId = Field(alias="_id")
    chat_id: str
    sender_id: PyObjectId
    content: str
    created_at: datetime
    is_group: bool = False

    class Config:
        json_encoders = {ObjectId: str}
