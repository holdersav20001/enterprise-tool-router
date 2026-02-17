from pydantic import BaseModel

class Settings(BaseModel):
    service_name: str = "enterprise-tool-router"
    environment: str = "dev"

    # Week 4 Commit 27: Query storage settings
    query_retention_days: int = 30        # Days to keep query history
    cache_size_limit_mb: int = 1          # Max size to cache (MB)
    cache_ttl_seconds: int = 1800         # Redis TTL (30 minutes)

    @property
    def cache_size_limit_bytes(self) -> int:
        """Convert MB to bytes."""
        return self.cache_size_limit_mb * 1_048_576

settings = Settings()
