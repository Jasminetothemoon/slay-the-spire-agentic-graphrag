import argparse
import importlib
import json
import platform
import sys
from pathlib import Path
from typing import Callable, List, Tuple


ROOT = Path(__file__).resolve().parents[1]
RECOMMENDED_MIN = (3, 11)
RECOMMENDED_MAX = (3, 12)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


CheckResult = Tuple[str, bool, str]


def check_python_version() -> CheckResult:
    version = sys.version_info
    version_text = platform.python_version()
    if RECOMMENDED_MIN <= (version.major, version.minor) <= RECOMMENDED_MAX:
        return ("python_version", True, f"Python {version_text} is within the recommended range.")
    return (
        "python_version",
        False,
        f"Python {version_text} detected. Use Python 3.11 or 3.12 for this project; newer versions may miss compatible wheels.",
    )


def check_import(module_name: str) -> CheckResult:
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        return (f"import:{module_name}", False, f"{type(exc).__name__}: {exc}")
    version = getattr(module, "__version__", "installed")
    return (f"import:{module_name}", True, str(version))


def check_path(path: str) -> CheckResult:
    target = ROOT / path
    if target.exists():
        return (f"path:{path}", True, "found")
    return (f"path:{path}", False, "missing")


def check_json(path: str) -> CheckResult:
    target = ROOT / path
    if not target.exists():
        return (f"json:{path}", False, "missing")
    try:
        with open(target, "r", encoding="utf-8") as f:
            json.load(f)
    except Exception as exc:
        return (f"json:{path}", False, f"{type(exc).__name__}: {exc}")
    return (f"json:{path}", True, "valid JSON")


def check_api_import() -> CheckResult:
    try:
        importlib.import_module("api.main")
    except Exception as exc:
        return ("api_import", False, f"{type(exc).__name__}: {exc}")
    return ("api_import", True, "api.main imports successfully")


def run_checks(include_api: bool) -> List[CheckResult]:
    checks: List[Callable[[], CheckResult]] = [
        check_python_version,
        lambda: check_import("pydantic"),
        lambda: check_import("fastapi"),
        lambda: check_import("uvicorn"),
        lambda: check_import("langgraph"),
        lambda: check_import("neo4j"),
        lambda: check_import("bs4"),
        lambda: check_path("requirements.txt"),
        lambda: check_path("api/main.py"),
        lambda: check_path("web/index.html"),
        lambda: check_json("data/public_full_data.json"),
        lambda: check_json("data/public_eval_cases.json"),
    ]
    if include_api:
        checks.append(check_api_import)
    return [check() for check in checks]


def print_results(results: List[CheckResult]) -> None:
    width = max(len(name) for name, _, _ in results)
    for name, ok, detail in results:
        marker = "PASS" if ok else "FAIL"
        print(f"{marker} {name.ljust(width)} {detail}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check whether the local development environment can run this project.")
    parser.add_argument("--skip-api-import", action="store_true", help="Skip importing api.main when FastAPI dependencies are not installed yet.")
    args = parser.parse_args()

    results = run_checks(include_api=not args.skip_api_import)
    print_results(results)
    if any(not ok for _, ok, _ in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
