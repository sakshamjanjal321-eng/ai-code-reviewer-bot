import os
import time
import logging
from collections import defaultdict
from fastapi import Request, HTTPException

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self, requests_limit: int = 20, window_seconds: int = 60):
        self.requests_limit = requests_limit
        self.window_seconds = window_seconds
        self.history = defaultdict(list)

    def is_rate_limited(self, ip: str) -> bool:
        now = time.time()
        # Filter out timestamps older than the sliding window
        self.history[ip] = [t for t in self.history[ip] if now - t < self.window_seconds]
        
        if len(self.history[ip]) >= self.requests_limit:
            return True
        
        self.history[ip].append(now)
        return False

# Initialize a global rate limiter instance
# Limit defaults to 20 requests per minute unless configured via environment
limit = int(os.getenv("RATE_LIMIT_PER_MINUTE", "20"))
limiter = RateLimiter(requests_limit=limit, window_seconds=60)

async def rate_limit_dependency(request: Request):
    # Extract client IP, checking first for proxy-forwarded IP headers
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        ip = forwarded_for.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else "unknown"

    if limiter.is_rate_limited(ip):
        logger.warning(f"Rate limit exceeded for IP: {ip}. Limit: {limit} req/min.")
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please try again later."
        )
