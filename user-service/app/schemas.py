from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class TokenRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)
    device_name: str | None = Field(default="api-token", max_length=100)


class UserInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr


class TokenIssued(BaseModel):
    token: str
    token_type: str
    expires_at: datetime
    user: UserInfo
