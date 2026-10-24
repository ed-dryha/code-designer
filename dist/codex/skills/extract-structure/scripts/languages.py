"""Extension -> tree-sitter-language-pack grammar name (tier-1 languages)."""

EXT_TO_LANG = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".cs": "csharp",
    ".go": "go",
    ".rs": "rust",
    ".php": "php",
    ".rb": "ruby",
}


def language_for(path: str):
    import os
    return EXT_TO_LANG.get(os.path.splitext(path)[1].lower())
