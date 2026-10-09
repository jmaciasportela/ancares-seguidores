"""Sube la versión "patch" de la PWA (frontend/package.json y package-lock.json).

Lo ejecuta el hook .githooks/pre-commit en cada commit: con una versión nueva
cambia el bundle, por tanto el service worker, y los móviles que tienen la app
instalada se actualizan. Uso manual: python3 scripts/bump_version.py [major|minor|patch]
"""
import json
import sys
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"


def bump(version: str, part: str) -> str:
    major, minor, patch = (int(x) for x in version.split("."))
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    part = sys.argv[1] if len(sys.argv) > 1 else "patch"
    pkg_path = FRONTEND / "package.json"
    pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
    new = bump(pkg["version"], part)
    pkg["version"] = new
    write_json(pkg_path, pkg)

    lock_path = FRONTEND / "package-lock.json"
    if lock_path.exists():
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        lock["version"] = new
        if "" in lock.get("packages", {}):
            lock["packages"][""]["version"] = new
        write_json(lock_path, lock)
    print(new)


if __name__ == "__main__":
    main()
