import os
import sys
# Add current directory to path to support absolute-style module imports from current folder
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import json
import logging
import hmac
import hashlib
from datetime import datetime
from typing import Optional, List
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from github_handler import GitHubHandler, get_pr_diff, post_review_comment
from reviewer import Reviewer, ReviewResult, review_code
from rate_limiter import rate_limit_dependency
from history_store import history_store

# Configure logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI(title="AI Code Reviewer Bot", version="1.0.0")

# CORS middleware for local testing/deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_headers=["*"],
    allow_methods=["*"],
)

# Resolve Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_FILE = os.path.join(BASE_DIR, "reviews_history.json")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

# Input Schemas
class PRReviewRequest(BaseModel):
    repo: str
    pr_number: int
    github_token: Optional[str] = None

class DiffReviewRequest(BaseModel):
    diff_text: str

# Helper functions for history storage delegating to unified datastore abstraction
def load_history() -> List[dict]:
    return history_store.load_history()

def save_history(entry: dict):
    history_store.save_history(entry)

async def run_and_post_pr_review(req: PRReviewRequest):
    """
    Background worker task to fetch PR details, run Gemini review, and post to GitHub.
    """
    token = req.github_token or os.getenv("GITHUB_PAT")
    if not token:
        logger.error("No GitHub token available. Review aborted.")
        return
        
    try:
        gh = GitHubHandler(token)
        reviewer = Reviewer()
        
        # 1. Fetch Diff
        diff_text = await gh.get_pr_diff(req.repo, req.pr_number)
        
        # 2. Parse Diff for valid comment line numbers
        valid_lines = gh.parse_diff(diff_text)
        
        # 3. AI Review
        review_res: ReviewResult = reviewer.review_diff(diff_text, valid_lines)
        
        # 4. Post to GitHub
        comments_list = [c.model_dump() for c in review_res.comments]
        success = await gh.post_review(req.repo, req.pr_number, review_res.summary, comments_list)
        
        # Count severities
        errors = sum(1 for c in comments_list if c["severity"] == "error")
        warnings = sum(1 for c in comments_list if c["severity"] == "warning")
        infos = sum(1 for c in comments_list if c["severity"] == "info")
        
        # 5. Save History
        history_entry = {
            "id": f"pr-{int(datetime.utcnow().timestamp())}",
            "repo": req.repo,
            "pr_number": req.pr_number,
            "type": "github_pr",
            "summary": review_res.summary,
            "comment_count": len(comments_list),
            "errors": errors,
            "warnings": warnings,
            "infos": infos,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "success" if success else "failed_post"
        }
        save_history(history_entry)
        
    except Exception as e:
        logger.error(f"Error in background PR review execution: {e}")
        history_entry = {
            "id": f"pr-err-{int(datetime.utcnow().timestamp())}",
            "repo": req.repo,
            "pr_number": req.pr_number,
            "type": "github_pr",
            "summary": f"Failed with error: {str(e)}",
            "comment_count": 0,
            "errors": 0,
            "warnings": 0,
            "infos": 0,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "error"
        }
        save_history(history_entry)

# Endpoints
@app.post("/api/review", dependencies=[Depends(rate_limit_dependency)])
async def trigger_pr_review(req: PRReviewRequest, background_tasks: BackgroundTasks):
    """
    Triggers an asynchronous code review for a GitHub Pull Request.
    Useful for webhook trigger from GitHub Actions.
    """
    token = req.github_token or os.getenv("GITHUB_PAT")
    if not token:
        raise HTTPException(status_code=400, detail="GitHub Token is required (pass in request or configure GITHUB_PAT on server)")
        
    background_tasks.add_task(run_and_post_pr_review, req)
    return {"message": f"Review process initiated for {req.repo} PR #{req.pr_number} in background."}

@app.post("/api/review-diff", dependencies=[Depends(rate_limit_dependency)])
async def trigger_diff_review(req: DiffReviewRequest):
    """
    Reviews a raw git diff and returns the structured suggestions. Used by the simulation dashboard.
    """
    if not req.diff_text.strip():
        raise HTTPException(status_code=400, detail="Diff content cannot be empty")
        
    try:
        gh = GitHubHandler()
        reviewer = Reviewer()
        
        # Parse diff to identify lines we can comment on
        valid_lines = gh.parse_diff(req.diff_text)
        
        # AI Review
        review_res: ReviewResult = reviewer.review_diff(req.diff_text, valid_lines)
        
        comments_list = [c.model_dump() for c in review_res.comments]
        errors = sum(1 for c in comments_list if c["severity"] == "error")
        warnings = sum(1 for c in comments_list if c["severity"] == "warning")
        infos = sum(1 for c in comments_list if c["severity"] == "info")
        
        # Save Simulation in History
        history_entry = {
            "id": f"sim-{int(datetime.utcnow().timestamp())}",
            "repo": "Simulation Mode",
            "pr_number": 0,
            "type": "simulation",
            "summary": review_res.summary,
            "comment_count": len(comments_list),
            "errors": errors,
            "warnings": warnings,
            "infos": infos,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "success"
        }
        save_history(history_entry)
        
        return review_res
    except Exception as e:
        logger.error(f"Error in diff review simulator: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/history")
def get_review_history():
  """
  Returns the history of recent code reviews.
  """
  return load_history()


@app.post("/webhook", dependencies=[Depends(rate_limit_dependency)])
async def github_webhook(request: Request):
  # Verify webhook signature if secret is configured
  body = await request.body()
  secret_str = os.getenv("GITHUB_WEBHOOK_SECRET")

  if secret_str:
    secret = secret_str.encode()
    signature = request.headers.get("X-Hub-Signature-256", "")

    expected = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, signature):
      raise HTTPException(status_code=401, detail="Invalid signature")
  else:
    logger.warning("GITHUB_WEBHOOK_SECRET not configured. HMAC validation bypassed.")

  payload = await request.json()

  # Only trigger on PR open or new commits
  if payload.get("action") in ["opened", "synchronize"]:
    repo = payload["repository"]["full_name"]
    pr_number = payload["pull_request"]["number"]

    # Get code diff using synchronous helper
    diff = get_pr_diff(repo, pr_number)

    # Get AI review using synchronous helper
    review = review_code(diff)

    # Post comment on PR
    post_review_comment(repo, pr_number, f"## 🤖 AI Code Review\n\n{review}")

    # Count lines and log into dashboard history
    history_entry = {
        "id": f"webhook-{int(datetime.utcnow().timestamp())}",
        "repo": repo,
        "pr_number": pr_number,
        "type": "github_pr",
        "summary": review,
        "comment_count": 0,
        "errors": 0,
        "warnings": 0,
        "infos": 0,
        "timestamp": datetime.utcnow().isoformat(),
        "status": "success",
    }
    save_history(history_entry)

  return {"status": "ok"}


# Serve static files for frontend Dashboard
if not os.path.exists(FRONTEND_DIR):
  os.makedirs(FRONTEND_DIR)

app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

