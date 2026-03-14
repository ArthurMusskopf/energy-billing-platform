from pydantic import BaseModel


class HealthResponse(BaseModel):
    ok: bool
    app: str
    env: str
    version: str