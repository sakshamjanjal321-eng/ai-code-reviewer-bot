import re
import logging
from typing import Dict, Set, List, Tuple
import httpx

logger = logging.getLogger(__name__)

class GitHubHandler:
    def __init__(self, token: str = None):
        self.token = token
        # Setup headers
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            # GitHub actions GITHUB_TOKEN and PATs work with Bearer or token prefix
            self.headers["Authorization"] = f"token {self.token}"

    async def get_pr_diff(self, repo: str, pr_number: int) -> str:
        """
        Fetches the raw git diff of a Pull Request.
        """
        url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
        
        # We need the diff representation
        diff_headers = self.headers.copy()
        diff_headers["Accept"] = "application/vnd.github.v3.diff"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=diff_headers, timeout=30.0)
            if response.status_code != 200:
                logger.error(f"Failed to fetch PR diff: {response.status_code} - {response.text}")
                response.raise_for_status()
            return response.text

    def parse_diff(self, diff_text: str) -> Dict[str, Set[int]]:
        """
        Parses a unified git diff and extracts the set of line numbers in the new file
        that represent actual additions or modifications (lines prefixed with '+').
        
        Returns:
            Dict[str, Set[int]]: Mapping of filename -> set of valid line numbers.
        """
        valid_lines: Dict[str, Set[int]] = {}
        current_file = None
        current_line_num = 0
        
        # Matches: @@ -old_start,old_len +new_start,new_len @@
        # or @@ -old_start +new_start @@
        hunk_re = re.compile(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@')
        
        lines = diff_text.splitlines()
        for line in lines:
            if line.startswith("--- "):
                # Old file header, ignore
                continue
            elif line.startswith("+++ "):
                # New file header, extract path
                # e.g., +++ b/backend/main.py or +++ /dev/null
                filepath = line[4:].strip()
                if filepath == "/dev/null":
                    current_file = None
                else:
                    # Strip 'b/' prefix if present
                    if filepath.startswith("b/"):
                        filepath = filepath[2:]
                    current_file = filepath
                    valid_lines[current_file] = set()
                continue
            
            if current_file is None:
                continue
                
            hunk_match = hunk_re.match(line)
            if hunk_match:
                # We found a hunk header, start tracking line numbers in the new file
                current_line_num = int(hunk_match.group(1))
                continue
            
            # If we are inside a hunk, process line symbols
            if line.startswith("+"):
                valid_lines[current_file].add(current_line_num)
                current_line_num += 1
            elif line.startswith("-"):
                # Deleted line, does not exist in the new file, so we don't increment new file line counter
                continue
            elif line.startswith(" "):
                # Unchanged context line, increments the new file line counter
                current_line_num += 1
            elif line.startswith("\\"):
                # Metadata line (e.g. \ No newline at end of file), ignore
                continue

        # Filter out empty files
        return {k: v for k, v in valid_lines.items() if v}

    async def post_review(self, repo: str, pr_number: int, summary: str, comments: List[dict]) -> bool:
        """
        Posts the review comments and summary to the GitHub Pull Request.
        """
        url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews"
        
        # Prepare comments in GitHub format
        github_comments = []
        for comment in comments:
            github_comments.append({
                "path": comment["file_path"],
                "line": comment["line_number"],
                "body": f"### [{comment['severity'].upper()}] Suggestion\n\n{comment['comment']}",
                "side": "RIGHT"
            })
            
        payload = {
            "body": summary,
            "event": "COMMENT",
            "comments": github_comments
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=self.headers, json=payload, timeout=20.0)
            if response.status_code not in (200, 201):
                logger.error(f"Failed to post GitHub review: {response.status_code} - {response.text}")
                return False
            
            logger.info(f"Successfully posted PR review to PR #{pr_number}")
            return True

def get_pr_diff(repo: str, pr_number: int, token: str = None) -> str:
    """
    Synchronous wrapper to retrieve the raw diff of a Pull Request.
    """
    import os
    if not token:
        token = os.getenv("GITHUB_PAT") or os.getenv("GITHUB_TOKEN")
        
    headers = {
        "Accept": "application/vnd.github.v3.diff",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"token {token}"
        
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    with httpx.Client() as client:
        response = client.get(url, headers=headers, timeout=30.0)
        response.raise_for_status()
        return response.text

def post_review_comment(repo: str, pr_number: int, comment: str, token: str = None) -> bool:
    """
    Synchronous wrapper to post a comment on a Pull Request.
    """
    import os
    if not token:
        token = os.getenv("GITHUB_PAT") or os.getenv("GITHUB_TOKEN")
        
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"token {token}"
        
    # Standard issue comment endpoint (PRs are issues)
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    payload = {"body": comment}
    with httpx.Client() as client:
        response = client.post(url, headers=headers, json=payload, timeout=20.0)
        if response.status_code not in (200, 201):
            logger.error(f"Failed to post PR comment: {response.status_code} - {response.text}")
            return False
        return True

