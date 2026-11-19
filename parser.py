import csv
import json
from pathlib import Path

# Optional dependency: only needed if we encounter .xlsx files and pandas is installed.
try:
    import pandas as pd
except ImportError:
    pd = None


def inspect_file(path: Path, root: Path) -> dict:
    """Inspect a single file and return a lightweight summary/metadata record."""
    rel_path = str(path.relative_to(root))
    ext = path.suffix.lower()
    info = {
        "path": rel_path,
        "ext": ext,
        "size_bytes": path.stat().st_size,
        "status": "indexed",
    }

    try:
        if ext == ".json":
            # Load JSON and record top-level type + up to 25 dictionary keys.
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            info["summary"] = {
                "type": type(data).__name__,
                "keys": list(data.keys())[:25] if isinstance(data, dict) else None,
            }
        elif ext == ".csv":
            # Read just the header row and first 5 data rows instead of the whole file.
            with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
                reader = csv.reader(f)
                headers = next(reader, [])
                sample_rows = [row for _, row in zip(range(5), reader)]
            info["summary"] = {"headers": headers, "sample_rows": sample_rows}
        elif ext == ".xlsx" and pd is not None:
            # Preview up to 10 sheets and the first 5 rows per sheet; replace NaNs for JSON safety.
            excel = pd.ExcelFile(path)
            sheets_preview = {}
            for sheet in excel.sheet_names[:10]:
                df = excel.parse(sheet, nrows=5)
                sheets_preview[sheet] = {
                    "columns": [str(c) for c in df.columns],
                    "sample_rows": df.fillna("").to_dict(orient="records"),
                }
            info["summary"] = {"sheet_names": excel.sheet_names, "sheets": sheets_preview}
        elif ext in {".txt", ".md", ".log", ".eml", ".py", ".cc", ".html"}:
            # Capture character count and a short text preview for text/code files.
            text = path.read_text(encoding="utf-8", errors="replace")
            info["preview"] = text[:1500]
            info["char_count"] = len(text)
        else:
            # Keep file metadata for unsupported/binary formats so downstream steps still see them.
            info["status"] = "metadata_only"
    except Exception as exc:
        # Isolate per-file errors so one bad file doesn't crash the whole workspace scan.
        info["status"] = "parse_error"
        info["error"] = str(exc)

    return info


def build_state(workspace_dir: str = ".") -> dict:
    """Recursively scan a workspace directory and build the initial state dictionary."""
    root = Path(workspace_dir).resolve()
    files = []

    # Sort paths for deterministic output and skip project_state.json so we don't re-index it.
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.name != "project_state.json":
            files.append(inspect_file(p, root))

    return {
        "workspace": str(root),
        "file_count": len(files),
        "files": files,
        "parameters": {},
        "execution_results": [],
    }


if __name__ == "__main__":
    # Run standalone against the current directory and write project_state.json.
    state = build_state(".")
    Path("project_state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(f"Indexed {state['file_count']} files into project_state.json")