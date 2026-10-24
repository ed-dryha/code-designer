"""Stdlib-only helpers shared by extractor, validator and verifier."""
import hashlib

IGNORE_DIRS = (".git", "node_modules", "vendor", ".venv", "dist", "build")
MAX_BYTES = 1048576


def file_sha256(data: bytes) -> str:
    """Full hex sha256 of raw file bytes."""
    return hashlib.sha256(data).hexdigest()


def normalize_ws(text: str) -> str:
    """Collapse all whitespace runs (including newlines) to single spaces."""
    return " ".join(text.split())


def symbol_hash(text: str) -> str:
    """12-hex sha256 of whitespace-normalized span text."""
    return hashlib.sha256(normalize_ws(text).encode("utf-8")).hexdigest()[:12]


def normalize_lines(text: str) -> str:
    """Verifier normalization: CRLF->LF, strip indentation/trailing space, collapse runs."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(" ".join(ln.split()) for ln in lines)
