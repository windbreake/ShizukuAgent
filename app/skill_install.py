from __future__ import annotations

import json
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from app.paths import SKILLS_DIR, ensure_runtime_dirs
from app.skill_manager import get_skill_manager


def _safe_id(raw: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", str(raw or "").strip())
    return text.strip("-_.") or "skill"


def search_github_skills(query: str = "", page: int = 1, page_size: int = 24) -> dict[str, Any]:
    page = max(int(page or 1), 1)
    page_size = max(1, min(int(page_size or 24), 50))
    terms = " ".join(part for part in [query.strip(), "SKILL.md", "topic:agent-skills"] if part)
    url = (
        "https://api.github.com/search/repositories"
        f"?q={quote(terms)}&page={page}&per_page={page_size}&sort=stars&order=desc"
    )
    errors: list[str] = []
    items: list[dict[str, Any]] = []
    total = 0
    try:
        request = Request(url, headers={"User-Agent": "ShizukuClaw", "Accept": "application/vnd.github+json"})
        with urlopen(request, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
        total = int(payload.get("total_count") or 0)
        for repo in payload.get("items") or []:
            items.append(
                {
                    "id": repo.get("full_name"),
                    "name": repo.get("name"),
                    "description": repo.get("description") or "",
                    "external_url": repo.get("html_url") or "",
                    "source": "github",
                    "stars": repo.get("stargazers_count") or 0,
                }
            )
    except Exception as exc:
        errors.append(str(exc))
    return {
        "success": not errors,
        "code": 0 if not errors else 1,
        "items": items,
        "data": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "has_more": page * page_size < total,
        "source": "github",
        "message": "GitHub 仓库搜索结果" if not errors else f"GitHub 搜索失败: {errors[0]}",
        "diagnostics": {
            "cache": {"count": len(items), "age_seconds": 0},
            "sources": [{"source": "github", "ok": not errors, "count": len(items)}],
            "errors": errors,
        },
    }


def install_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    ensure_runtime_dirs()
    url = str(payload.get("url") or payload.get("external_url") or "").strip()
    skill_id = _safe_id(payload.get("skill_id") or payload.get("name") or Path(urlparse(url).path).stem or "imported")
    name = str(payload.get("name") or skill_id)
    description = str(payload.get("description") or url or "Imported skill")
    dest = SKILLS_DIR / skill_id
    dest.mkdir(parents=True, exist_ok=True)
    source = "local"
    if url.startswith("http://") or url.startswith("https://"):
        source = "url"
        try:
            _download_skill(url, dest, skill_id, name, description)
        except Exception as exc:
            _write_placeholder(dest, skill_id, name, description, url, error=str(exc))
            source = "placeholder"
    else:
        _write_placeholder(dest, skill_id, name, description, url)
    get_skill_manager().reload()
    return {"success": True, "skill_id": skill_id, "path": f"plugins/skills/{skill_id}", "source": source}


def install_uploaded_zip(file_path: Path, fallback_name: str = "") -> dict[str, Any]:
    ensure_runtime_dirs()
    skill_id = _safe_id(fallback_name or file_path.stem)
    dest = SKILLS_DIR / skill_id
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(file_path, "r") as zf:
        zf.extractall(dest)
    if not (dest / "SKILL.md").exists():
        nested = next(dest.rglob("SKILL.md"), None)
        if nested and nested.parent != dest:
            for item in nested.parent.iterdir():
                shutil.move(str(item), dest / item.name)
    if not (dest / "SKILL.md").exists():
        _write_placeholder(dest, skill_id, skill_id, "Uploaded skill", "")
    get_skill_manager().reload()
    return {"success": True, "skill_id": skill_id, "path": f"plugins/skills/{skill_id}"}


def _download_skill(url: str, dest: Path, skill_id: str, name: str, description: str) -> None:
    parsed = urlparse(url)
    if "github.com" in parsed.netloc and "/blob/" in parsed.path:
        url = url.replace("https://github.com/", "https://raw.githubusercontent.com/").replace("/blob/", "/")
    request = Request(url, headers={"User-Agent": "ShizukuClaw"})
    with urlopen(request, timeout=20) as resp:
        body = resp.read()
        content_type = str(resp.headers.get("Content-Type") or "")
    if url.lower().endswith(".zip") or "zip" in content_type:
        zip_path = dest / "import.zip"
        zip_path.write_bytes(body)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(dest)
        zip_path.unlink(missing_ok=True)
        return
    text = body.decode("utf-8", errors="replace")
    if url.lower().endswith(".md") or text.lstrip().startswith("---") or text.lstrip().startswith("#"):
        (dest / "SKILL.md").write_text(text, encoding="utf-8")
        return
    _write_placeholder(dest, skill_id, name, description, url)


def _write_placeholder(dest: Path, skill_id: str, name: str, description: str, url: str, error: str = "") -> None:
    dest.mkdir(parents=True, exist_ok=True)
    note = f"来源: {url}" if url else "本地导入"
    if error:
        note += f"\n下载失败，已创建占位 Skill：{error}"
    (dest / "SKILL.md").write_text(
        (
            "---\n"
            f"id: {skill_id}\n"
            f"name: {name}\n"
            f"description: {description}\n"
            "version: 0.1.0\n"
            "persona: false\n"
            "enabled: true\n"
            "---\n\n"
            f"# {name}\n\n{note}\n"
        ),
        encoding="utf-8",
    )
    (dest / "source.json").write_text(
        json.dumps({"url": url, "error": error}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
