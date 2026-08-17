from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    company_name: str = Field(min_length=1, max_length=255)
    company_website: str = Field(min_length=1, max_length=255)
    product_description: str = Field(min_length=1, max_length=1000)
    industry: str = Field(min_length=1, max_length=255)
    target_market: str = Field(min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10)
    new_password: str = Field(min_length=8, max_length=128)


class MessageResponse(BaseModel):
    message: str


class SignupResponse(BaseModel):
    message: str
    workspace_id: str
    onboarding_completed: bool
    next_step: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_at: datetime
