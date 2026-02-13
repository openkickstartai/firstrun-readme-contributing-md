"""Tests for FirstRun scanning engine."""
import json
import tempfile
from pathlib import Path
from firstrun import (
    extract_code_blocks, extract_file_refs, extract_urls,
    parse_makefile_targets, parse_npm_scripts, scan, format_sarif,
)


def test_extract_code_blocks_parses_lang_and_content():
    md = "# Setup\n\n```bash\nmake install\npip install -e .\n```\n\nThen:\n\n```python\nprint('hi')\n```\n"
    blocks = extract_code_blocks(md)
    assert len(blocks) == 2
    assert blocks[0]["lang"] == "bash"
    assert "make install" in blocks[0]["content"]
    assert blocks[1]["lang"] == "python"
    assert blocks[0]["line"] == 3


def test_extract_file_refs_finds_dotfiles_and_paths():
    md = "Copy `config.yaml` and edit `.env.example` then see `src/main.py`.\n"
    refs = extract_file_refs(md)
    paths = [r["path"] for r in refs]
    assert "config.yaml" in paths
    assert ".env.example" in paths
    assert "src/main.py" in paths


def test_extract_urls_captures_markdown_links():
    md = "See [docs](https://example.com/docs) and https://github.com/org/repo.\n"
    urls = extract_urls(md)
    assert len(urls) == 2
    assert urls[0]["url"] == "https://example.com/docs"
    assert urls[1]["url"] == "https://github.com/org/repo"


def test_parse_makefile_targets_extracts_all():
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "Makefile").write_text("install:\n\tpip install .\n\ntest:\n\tpytest\n\nclean:\n\trm -rf dist\n")
        targets = parse_makefile_targets(d)
        assert targets == {"install", "test", "clean"}


def test_parse_makefile_missing_returns_empty():
    with tempfile.TemporaryDirectory() as d:
        assert parse_makefile_targets(d) == set()


def test_parse_npm_scripts():
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "package.json").write_text('{"scripts": {"start": "node .", "test": "jest"}}')
        assert parse_npm_scripts(d) == {"start", "test"}


def test_scan_detects_missing_file_ref():
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "README.md").write_text("# Project\n\nCopy `.env.example` to your dir.\n")
        result = scan(d)
        categories = [i.category for i in result.issues]
        assert "file-ref" in categories
        assert result.score < 100


def test_scan_detects_missing_make_target():
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "Makefile").write_text("build:\n\tgo build .\n")
        (Path(d) / "README.md").write_text("# Dev\n\n```bash\nmake dev-setup\nmake build\n```\n")
        result = scan(d)
        msgs = [i.message for i in result.issues]
        assert any("dev-setup" in m for m in msgs)
        assert not any("build" in m and "not found" in m for m in msgs)


def test_scan_detects_missing_npm_script():
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "package.json").write_text('{"scripts": {"start": "node .", "test": "jest"}}')
        (Path(d) / "README.md").write_text("# Dev\n\n```bash\nnpm run dev\nnpm run test\n```\n")
        result = scan(d)
        msgs = [i.message for i in result.issues]
        assert any("dev" in m for m in msgs)
        assert not any("test" in m and "not found" in m for m in msgs)


def test_scan_clean_repo_scores_100():
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "README.md").write_text("# Project\n\nA simple project with no special setup.\n")
        result = scan(d)
        assert result.score == 100
        assert len(result.issues) == 0


def test_scan_no_docs_scores_zero():
    with tempfile.TemporaryDirectory() as d:
        result = scan(d)
        assert result.score == 0
        assert any(i.category == "missing" for i in result.issues)


def test_format_sarif_valid_structure():
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "README.md").write_text("# Hi\n\nSee `.env.example` for config.\n")
        result = scan(d)
        sarif = format_sarif(result)
        assert sarif["version"] == "2.1.0"
        assert len(sarif["runs"]) == 1
        assert sarif["runs"][0]["tool"]["driver"]["name"] == "FirstRun"
        assert len(sarif["runs"][0]["results"]) > 0
