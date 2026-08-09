#!/usr/bin/env python3
from pathlib import Path
import re
import shutil
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "android" / "app" / "src" / "main" / "assets" / "www"
RUNTIME_COMMIT = "3355cdc9064d409ec1ece7bc8beddba20e80f30f"

VENDOR = {
    "react.production.min.js": "https://unpkg.com/react@18.3.1/umd/react.production.min.js",
    "react-dom.production.min.js": "https://unpkg.com/react-dom@18.3.1/umd/react-dom.production.min.js",
    "babel.min.js": "https://unpkg.com/@babel/standalone@7.29.0/babel.min.js",
}


def download(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "ArshiaEspanol-Android-Build/1.0"})
    with urllib.request.urlopen(req, timeout=30) as response, target.open("wb") as f:
        shutil.copyfileobj(response, f)


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    # Copy only the web app payload, not the Android project or repository metadata.
    shutil.copy2(ROOT / "index.html", OUT / "index.html")
    for name in ("data", "assets"):
        src = ROOT / name
        if src.exists():
            shutil.copytree(src, OUT / name)

    # Bundle the exact runtime used by the last known-good web build.
    runtime = subprocess.check_output(
        ["git", "show", f"{RUNTIME_COMMIT}:support.js"], cwd=ROOT, text=True
    )

    # Make React/ReactDOM/Babel local so app startup never waits on a CDN.
    runtime = runtime.replace(
        'var REACT_URL = "https://unpkg.com/react@18.3.1/umd/react.production.min.js";',
        'var REACT_URL = "https://app.local/vendor/react.production.min.js";'
    ).replace(
        'var REACT_DOM_URL = "https://unpkg.com/react-dom@18.3.1/umd/react-dom.production.min.js";',
        'var REACT_DOM_URL = "https://app.local/vendor/react-dom.production.min.js";'
    ).replace(
        'var BABEL_URL = "https://unpkg.com/@babel/standalone@7.29.0/babel.min.js";',
        'var BABEL_URL = "https://app.local/vendor/babel.min.js";'
    )
    (OUT / "support.js").write_text(runtime, encoding="utf-8")

    # Patch the Android copy only. The public web page remains unchanged.
    index_path = OUT / "index.html"
    index = index_path.read_text(encoding="utf-8")

    # Eliminate network font requests; Android's system font renders immediately.
    index = re.sub(r'<link rel="preconnect" href="https://fonts\.googleapis\.com">\s*', '', index)
    index = re.sub(r'<link href="https://fonts\.googleapis\.com[^>]+>\s*', '', index)

    # Pin the current stable Gemini models instead of moving aliases.
    index = index.replace("gemini-flash-lite-latest", "gemini-3.5-flash-lite")
    index = index.replace("gemini-flash-latest", "gemini-3.6-flash")

    # Gemini 3.x removed the old sampling knobs and uses thinkingLevel.
    index = index.replace(
        "generationConfig:{maxOutputTokens:maxTokens||1500,temperature:0.2,thinkingConfig:{thinkingBudget:0}}",
        "generationConfig:{maxOutputTokens:maxTokens||1500,thinkingConfig:{thinkingLevel:model==='gemini-3.6-flash'?'medium':'minimal'}}"
    )
    index = index.replace(
        "generationConfig:{temperature:0,thinkingConfig:{thinkingBudget:0}}",
        "generationConfig:{thinkingConfig:{thinkingLevel:model==='gemini-3.6-flash'?'medium':'minimal'}}"
    )

    index_path.write_text(index, encoding="utf-8")

    for filename, url in VENDOR.items():
        download(url, OUT / "vendor" / filename)

    print(f"Prepared fast local web bundle at {OUT}")


if __name__ == "__main__":
    main()
