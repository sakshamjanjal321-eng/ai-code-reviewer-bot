import os
import logging
from typing import Dict, Set, List
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from dotenv import load_dotenv

try:
    from .prompts import generate_review_prompt
except ImportError:
    from prompts import generate_review_prompt

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load env variables
load_dotenv()

# Schema definitions for Gemini Structured Outputs
class InlineComment(BaseModel):
    file_path: str = Field(description="The path of the file, matching exactly the diff filename.")
    line_number: int = Field(description="The line number in the NEW version of the file where the suggestion applies.")
    comment: str = Field(description="Constructive feedback, explaining the issue and recommending code adjustments. Use markdown.")
    severity: str = Field(description="The severity level: 'info', 'warning', or 'error'.")

class ReviewResult(BaseModel):
    summary: str = Field(description="A comprehensive markdown summary of the pull request review.")
    comments: List[InlineComment] = Field(default=[], description="List of inline comments for the modified lines.")

class Reviewer:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model_name = "gemini-2.5-flash"
        self._configured = False
        
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
            self._configured = True
            logger.info("Gemini API successfully configured using new google-genai client.")
        else:
            logger.warning("GEMINI_API_KEY not found in environment. Bot will run in simulation mode only.")

    def review_diff(self, diff_text: str, valid_lines: Dict[str, Set[int]]) -> ReviewResult:
        """
        Reviews the git diff using Google's Gemini LLM with Structured Outputs.
        """
        if not self._configured:
            # Return a simulated mock review if no API key is set, so the app runs without crashing
            logger.warning("Gemini API not configured, returning simulated review.")
            return self._generate_mock_review(valid_lines)

        try:
            # Construct the prompt with context
            prompt = generate_review_prompt(diff_text, valid_lines)
            
            # Generate structured response
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ReviewResult,
                    temperature=0.2,
                )
            )
            
            # Use client's auto-parsing or fallback to manual parsing of response.text
            parsed_result = None
            if hasattr(response, "parsed") and response.parsed:
                parsed_result = response.parsed
                
            if not parsed_result:
                result_json = response.text
                if result_json.startswith("```json"):
                    result_json = result_json.split("```json")[1].split("```")[0].strip()
                elif result_json.startswith("```"):
                    result_json = result_json.split("```")[1].split("```")[0].strip()
                parsed_result = ReviewResult.model_validate_json(result_json)
            
            # Post-processing: Filter suggestions to double-verify they only target valid lines
            filtered_comments = []
            for comment in parsed_result.comments:
                file_p = comment.file_path.strip()
                # Find matching filepath in keys (case-insensitive or exact match check)
                matching_file = None
                for k in valid_lines.keys():
                    if k.lower() == file_p.lower() or file_p.endswith(k) or k.endswith(file_p):
                        matching_file = k
                        break
                
                if matching_file and comment.line_number in valid_lines[matching_file]:
                    # Update comment path to exact matched path
                    comment.file_path = matching_file
                    filtered_comments.append(comment)
                else:
                    logger.warning(f"Discarding invalid comment on {comment.file_path}:{comment.line_number} (not in valid lines)")
            
            parsed_result.comments = filtered_comments
            return parsed_result

        except Exception as e:
            logger.error(f"Error during AI code review generation: {str(e)}")
            # Fallback mock/error description
            return ReviewResult(
                summary=f"### AI Code Review (Failed)\n\nAn error occurred while generating the review: {str(e)}",
                comments=[]
            )

    def _generate_mock_review(self, valid_lines: Dict[str, Set[int]]) -> ReviewResult:
        """
        Generates a fallback mock review when GEMINI_API_KEY is not configured.
        """
        comments = []
        for file_path, lines in valid_lines.items():
            if lines:
                # Suggest a mock comment on the first modified line
                target_line = sorted(list(lines))[0]
                comments.append(InlineComment(
                    file_path=file_path,
                    line_number=target_line,
                    comment="**[MOCK COMMENT]**\nThis is a mock suggestion for testing. Make sure to configure your `GEMINI_API_KEY` in the `.env` file to enable actual AI reviews.",
                    severity="info"
                ))
        
        return ReviewResult(
            summary="### ⚠️ Demonstration Mode (Gemini API Key Missing)\n\n"
                    "Your bot is running in demonstration/mock mode because no `GEMINI_API_KEY` was found. "
                    "Configure it in your environment or backend `.env` file to receive live code insights.\n\n"
                    "#### Simulated Findings:\n"
                    "- Mock review generated for all modified files.\n"
                    "- Verified diff parsing is functioning correctly.",
            comments=comments
        )

def review_code(diff_text: str) -> str:
    """
    Synchronous module-level function to review a diff and return a markdown review summary.
    """
    try:
        from .github_handler import GitHubHandler
    except ImportError:
        from github_handler import GitHubHandler
    gh = GitHubHandler()
    valid_lines = gh.parse_diff(diff_text)
    
    reviewer = Reviewer()
    result = reviewer.review_diff(diff_text, valid_lines)
    return result.summary

