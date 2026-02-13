"""FirstRun — Core scanning engine for contributor onboarding verification."""
import re
import json
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class Issue:
    file: str
    line: int
    category: str
    message: str


@dataclass
class ScanResult:
    issues: list = field(default_factory=list)
    score: int = 100


def extract_code_blocks(content):
    """Extract fenced code blocks with language tag and line number."""
    blocks = []
    for m in re.finditer(r'```(\w*)\n(.*?)```', content, re.DOTALL):
        line = content[: m.start()].count("\n") + 1
        blocks.append({"lang": m.group(1), "content": m.group(2), "line": line})
    return blocks


def extract_file_refs(content):
    """Extract backtick-quoted file path references."""
    refs = []
    for i, text in enumerate(content.split("\n")):
        for m in re.finditer(r"`([a-zA-Z0-9_./-]+\.[a-zA-Z0-9]+)`", text):
            p = m.group(1)
            if not p.startswith("http"):
                refs.append({"path": p, "line": i + 1})
    return refs


def extract_urls(content):
    """Extract all HTTP(S) URLs from text."""
    urls = []
    for i, text in enumerate(content.split("\n")):
        for m in re.finditer(r"https?://[^\s\)\]>\"'`]+", text):
            urls.append({"url": m.group(0).rstrip(".,;:"), "line": i + 1})
    return urls


def parse_makefile_targets(repo_path):
    """Parse Makefile and return set of target names."""
    mf = Path(repo_path) / "Makefile"
    if not mf.exists():
        return set()
    targets = set()
    for line in mf.read_text().split("\n"):
        m = re.match(r"^([a-zA-Z_][\w-]*)\s*:", line)
        if m:
            targets.add(m.group(1))
    return targets


def parse_npm_scripts(repo_path):
    """Parse package.json and return set of script names."""
    pkg = Path(repo_path) / "package.json"
    if not pkg.exists():
        return set()
    try:
        return set(json.loads(pkg.read_text()).get("scripts", {}).keys())
    except (json.JSONDecodeError, KeyError):
        return set()


def check_links(urls):
    """Check reachability of URLs. Returns list of broken ones."""
    import httpx
    broken = []
    with httpx.Client(timeout=10, follow_redirects=True) as client:
        for u in urls:
            try:
                r = client.head(u["url"])
                if r.status_code >= 400:
                    broken.append({**u, "status": r.status_code})
            except Exception:
                broken.append({**u, "status": 0})
    return broken


def scan_file(repo_path, filepath, content):
    """Scan a single markdown file and return list of Issues."""
    issues = []
    repo = Path(repo_path)
    for ref in extract_file_refs(content):
        if not (repo / ref["path"]).exists():
            issues.append(Issue(filepath, ref["line"], "file-ref",
                                f"Referenced file `{ref['path']}` not found"))
    make_targets = parse_makefile_targets(repo_path)
    npm_scripts = parse_npm_scripts(repo_path)
    for block in extract_code_blocks(content):
        if block["lang"] in ("bash", "sh", "shell", "console", ""):
            for t in re.findall(r"make\s+([\w-]+)", block["content"]):
                if make_targets and t not in make_targets:
                    issues.append(Issue(filepath, block["line"], "command",
                                        f"Makefile target `{t}` not found"))
            for s in re.findall(r"(?:npm|yarn|pnpm)\s+run\s+([\w:-]+)", block["content"]):
                if npm_scripts and s not in npm_scripts:
                    issues.append(Issue(filepath, block["line"], "command",
                                        f"npm script `{s}` not found in package.json"))
    return issues


def scan(repo_path, check_urls_flag=False):
    """Scan a repository's documentation for onboarding issues."""
    repo = Path(repo_path)
    result = ScanResult()
    md_files = []
    for name in ["README.md", "CONTRIBUTING.md", "SETUP.md", "INSTALL.md"]:
        p = repo / name
        if p.exists():
            md_files.append((name, p.read_text()))
    docs_dir = repo / "docs"
    if docs_dir.is_dir():
        for p in docs_dir.rglob("*.md"):
            md_files.append((str(p.relative_to(repo)), p.read_text()))
    if not md_files:
        result.issues.append(Issue(".", 0, "missing", "No documentation found"))
        result.score = 0
        return result
    for filepath, content in md_files:
        result.issues.extend(scan_file(repo_path, filepath, content))
        if check_urls_flag:
            for bad in check_links(extract_urls(content)):
                s = bad["status"]
                msg = f"URL returned {s}: {bad['url']}" if s else f"Unreachable: {bad['url']}"
                result.issues.append(Issue(filepath, bad["line"], "dead-link", msg))
    penalty = sum(10 if i.category in ("command", "missing") else 5 for i in result.issues)
    result.score = max(0, 100 - penalty)
    return result


def format_sarif(result):
    """Format ScanResult as a SARIF 2.1.0 report dict."""
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {"name": "FirstRun", "version": "0.1.0"}},
            "results": [{
                "ruleId": i.category,
                "message": {"text": i.message},
                "level": "warning",
                "locations": [{"physicalLocation": {
                    "artifactLocation": {"uri": i.file},
                    "region": {"startLine": max(1, i.line)}
                }}]
            } for i in result.issues]
        }]
    }
