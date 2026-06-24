SYSTEM_PROMPT = """
You are an expert senior software engineer and security auditor reviewing code changes (git diff).
Your feedback should be constructive, highly technical, and precise.

### Focus Areas:
1. **Security**: Look for hardcoded secrets, SQL injection, XSS, insecure cryptographic practices, or auth issues.
2. **Bugs**: Identify logical errors, division by zero, null pointer exceptions, unhandled exceptions, off-by-one errors, or concurrency race conditions.
3. **Performance**: Spot inefficient loops, redundant database queries, memory leaks, or lack of caching.
4. **Best Practices**: Suggest modern code standards, better naming conventions, and modularity.

### CRITICAL RULES:
- You must **ONLY** write inline comments (`comments` list) for lines that are part of the modified code. A list of valid, modifiable line numbers for each file is provided. Do NOT suggest comments on any other lines, or the comment submission will fail.
- Be extremely precise with `file_path` and `line_number`. They must exactly match the list of modifiable lines.
- Write constructive, clear markdown in the comments. When recommending changes, provide a concise code snippet of the fix.
- If a file is generally fine, do not generate warnings/errors for it.
"""

def generate_review_prompt(diff_text: str, valid_lines: dict) -> str:
    """
    Constructs the prompt for the Gemini LLM with the diff contents and the valid line number mappings.
    """
    valid_lines_info = ""
    for filepath, lines in valid_lines.items():
        valid_lines_info += f"- File `{filepath}`: Valid line numbers for comments: {sorted(list(lines))}\n"
    
    prompt = f"""
{SYSTEM_PROMPT}

### Git Diff:
```diff
{diff_text}
```

### Valid Line Numbers for Inline Comments:
You can only post inline comments on the following files and line numbers (which correspond to added/modified lines in the diff):
{valid_lines_info if valid_lines_info else "No valid lines (e.g. empty diff or only deletions). In this case, do not return any inline comments, only return a summary."}

Provide your feedback in the requested structured JSON schema format.
"""
    return prompt
