"""Surface legacy ~/.qlankr/registry.json contents.

This script does NOT write to the database. Legacy entries have no user_id
so we cannot safely auto-attribute them. The intended workflow:

1. Run this script.
2. Note the legacy projects.
3. Log into the new app as the appropriate user.
4. Add each repo URL via the Projects UI.
5. Re-trigger indexing on this machine.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> int:
    path = Path(os.environ.get("HOME", "~")).expanduser() / ".qlankr" / "registry.json"
    if not path.exists():
        print(f"No legacy registry found at {path}")
        return 0

    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        print(f"Could not parse {path}: {e}", file=sys.stderr)
        return 1

    if not data:
        print(f"{path} is empty.")
        return 0

    print(f"Legacy registry at {path} contains {len(data)} projects:\n")
    for key, meta in data.items():
        repo_name = meta.get("repo_name") or key
        path_ = meta.get("path", "?")
        print(f"  - {key}")
        print(f"      repo_name: {repo_name}")
        print(f"      path:      {path_}")
    print("\nNext step: log into the app as the user who owns each project")
    print("and re-add each repo URL via the Projects UI.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
