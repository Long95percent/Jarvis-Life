import os
import glob
from typing import Any, List, Dict
from pydantic import BaseModel, Field

from app.tools.base import ShadowLinkTool
from app.models.mcp import ToolCategory

class LocalSearchInput(BaseModel):
    query: str = Field(description="Search keyword or pattern to look for in local files")
    mode_id: str = Field(default="general", description="The current work mode ID to determine search scope")

class LocalSearchTool(ShadowLinkTool):
    name: str = "local_search"
    description: str = (
        "Search for keywords directly inside local files configured in the current WorkMode. "
        "Use this tool when the user asks you to find code, text, or information within their local folders."
    )
    args_schema: type[BaseModel] = LocalSearchInput
    category: ToolCategory = ToolCategory.KNOWLEDGE

    def _run(self, query: str, mode_id: str = "general") -> str:
        raise NotImplementedError("Use async version")

    async def _arun(self, query: str, mode_id: str = "general") -> str:
        # In a real scenario, we would inject the mode's resources via context.
        # For now, we will extract it from the agent request context if available.
        # But since tools don't directly get the request context in this base class, 
        # we will rely on the engine injecting `resources` into the tool or context.
        
        # Let's check if there are resources passed in the context
        resources = getattr(self, "context_resources", [])
        
        if not resources:
            return "No local folders or files are configured in this WorkMode for searching. Please add resources to the mode first."

        search_paths = []
        for res in resources:
            if res.get('type') in ['folder', 'file']:
                path = res.get('value', '').strip()
                if path and os.path.exists(path):
                    search_paths.append(path)

        if not search_paths:
            return "Configured resources do not exist on the disk or are not searchable (e.g., URLs or Apps)."

        results = []
        max_results = 20
        max_chars_per_match = 300
        
        # Basic text search implementation (no embeddings)
        for path in search_paths:
            if len(results) >= max_results:
                break
                
            if os.path.isfile(path):
                self._search_file(path, query, results, max_chars_per_match)
            elif os.path.isdir(path):
                for root, _, files in os.walk(path):
                    if len(results) >= max_results:
                        break
                    # Skip common heavy/binary dirs
                    if any(ignored in root for ignored in ['.git', 'node_modules', '__pycache__', 'venv', '.venv']):
                        continue
                        
                    for file in files:
                        if len(results) >= max_results:
                            break
                        # Only search likely text files
                        if not file.endswith(('.txt', '.md', '.py', '.js', '.ts', '.tsx', '.jsx', '.json', '.yml', '.yaml', '.java', '.c', '.cpp', '.h', '.hpp', '.cs', '.go', '.rs', '.rb', '.html', '.css', '.scss', '.less')):
                            continue
                            
                        file_path = os.path.join(root, file)
                        self._search_file(file_path, query, results, max_chars_per_match)

        if not results:
            return f"No matches found for '{query}' in the configured local paths."

        output = [f"Found {len(results)} matches for '{query}':\n"]
        for i, res in enumerate(results, 1):
            output.append(f"[{i}] File: {res['file']} (Line {res['line']})")
            output.append(f"    Content: {res['content']}")
            output.append("")

        if len(results) == max_results:
            output.append("\nNote: Search stopped early after reaching maximum result limit.")

        return "\n".join(output)

    def _search_file(self, file_path: str, query: str, results: List[Dict], max_chars: int):
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for i, line in enumerate(f, 1):
                    if query.lower() in line.lower():
                        content = line.strip()
                        if len(content) > max_chars:
                            content = content[:max_chars] + "..."
                        results.append({
                            "file": file_path,
                            "line": i,
                            "content": content
                        })
                        if len(results) >= 20: # global max inside loop
                            return
        except Exception:
            pass # Skip unreadable files
