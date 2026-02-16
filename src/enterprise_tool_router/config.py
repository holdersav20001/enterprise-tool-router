from pydantic import BaseModel

class Settings(BaseModel):
    service_name: str = "enterprise-tool-router"
    environment: str = "dev"

settings = Settings()
