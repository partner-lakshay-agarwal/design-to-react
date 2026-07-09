#!/usr/bin/env python3
"""
fetch_figma.py -- Standalone Figma design extractor (no MCP, stdlib only).

Fetches a Figma file (or a single node subtree) via the Figma REST API, saves the
raw JSON, and produces a compact, LLM-friendly design spec:

  - figma_raw.json  : raw API response (may be large -- do NOT hand-read)
  - figma_spec.json : machine spec (screens, color/shadow/typography tokens,
                      per-screen text + layout hints)
  - figma_spec.md   : human/LLM-readable summary (read this)

Optionally downloads one reference PNG per top-level screen for a visual compare loop.

Auth (token resolution order):
  1. --token argument
  2. FIGMA_TOKEN environment variable
  3. FIGMA_API_KEY environment variable
  4. FIGMA_TOKEN / FIGMA_API_KEY in a .env file in the current working directory

No third-party packages required (uses urllib only). Python 3.9+.

Usage:
  python fetch_figma.py --url "https://www.figma.com/design/KEY/Name?node-id=1-2" --out ./.design-cache
  python fetch_figma.py --file-key KEY --node-id 1:2 --out ./.design-cache
  python fetch_figma.py --url "<url>" --download-images --out ./.design-cache
  python fetch_figma.py --from-json ./.design-cache/figma_raw.json --out ./.design-cache
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

FIGMA_API = "https://api.figma.com/v1"

# Node types treated as candidate "screens" (top-level layouts).
SCREEN_TYPES = {"FRAME", "COMPONENT", "COMPONENT_SET", "SECTION"}


# --------------------------------------------------------------------------- #
# Token / env helpers
# --------------------------------------------------------------------------- #
def load_env_file(cwd: Path) -> dict:
    """Best-effort parse of a .env file in the current working directory."""
    env: dict = {}
    env_path = cwd / ".env"
    if not env_path.exists():
        return env
    for raw in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip().replace("\r", "")
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        env[key] = value
    return env


def resolve_token(cli_token: str | None) -> str:
    if cli_token:
        return cli_token.strip()
    for key in ("FIGMA_TOKEN", "FIGMA_API_KEY"):
        val = os.environ.get(key)
        if val:
            return val.strip()
    env = load_env_file(Path.cwd())
    for key in ("FIGMA_TOKEN", "FIGMA_API_KEY"):
        if env.get(key):
            return env[key].strip()
    die(
        "No Figma token found. Provide --token, or set FIGMA_TOKEN / FIGMA_API_KEY "
        "in the environment or a .env file. Never paste the token into chat."
    )
    return ""  # unreachable


# --------------------------------------------------------------------------- #
# URL parsing
# --------------------------------------------------------------------------- #
def parse_figma_url(url: str) -> tuple[str, str | None]:
    """Extract (file_key, node_id) from a Figma URL. node_id normalised to `a:b`."""
    m = re.search(r"figma\.com/(?:design|file|board|proto)/([A-Za-z0-9]+)", url)
    if not m:
        die(f"Could not find a Figma file key in URL: {url}")
    file_key = m.group(1)

    node_id: str | None = None
    q = urllib.parse.urlparse(url).query
    params = urllib.parse.parse_qs(q)
    if "node-id" in params and params["node-id"]:
        node_id = params["node-id"][0]
    if node_id:
        # URLs use `1-2`; the API expects `1:2`.
        node_id = node_id.replace("-", ":")
    return file_key, node_id


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
class RequestTooLarge(Exception):
    """Raised when the Figma API rejects a node fetch as too large."""


def http_get_json(url: str, token: str, timeout: int = 120, retries: int = 5) -> dict:
    """GET JSON with retry on transient timeouts. Raises RequestTooLarge on 400 size errors."""
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, headers={"X-Figma-Token": token})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="ignore")
            except Exception:
                pass
            if e.code == 400 and "too large" in body.lower():
                raise RequestTooLarge(body)
            if e.code == 403:
                die("Figma API 403 Forbidden -- token is invalid/expired or lacks access. "
                    "Regenerate the token at figma.com -> Settings -> Security.")
            if e.code == 404:
                die("Figma API 404 Not Found -- wrong file key, or the account cannot view "
                    f"this file. Details: {body[:300]}")
            if e.code == 429:
                # rate limited -- honour Retry-After if present, else exponential backoff
                last_err = e
                retry_after = e.headers.get("Retry-After") if e.headers else None
                wait = int(retry_after) if (retry_after and retry_after.isdigit()) else None
                if attempt < retries:
                    delay = wait if wait is not None else min(2 ** attempt, 30)
                    print(f"  Figma API 429 rate-limited -- waiting {delay}s, then retry "
                          f"{attempt + 1}/{retries} ...", file=sys.stderr, flush=True)
                    _sleep_backoff(attempt, wait)
                    continue
                die("Figma API 429 Too Many Requests -- rate limit persists. "
                    "Wait a minute and re-run.")
            die(f"Figma API HTTP {e.code}: {body[:400]}")
        except (urllib.error.URLError, TimeoutError) as e:
            last_err = e
            if attempt < retries:
                delay = min(2 ** attempt, 30)
                reason = getattr(e, "reason", e)
                print(f"  Network/timeout reaching Figma API ({reason}) -- retry "
                      f"{attempt + 1}/{retries} in {delay}s ...", file=sys.stderr, flush=True)
                _sleep_backoff(attempt)
                continue
            reason = getattr(e, "reason", e)
            die(f"Network error reaching Figma API after {retries + 1} tries: {reason}. "
                "Check connectivity/VPN/proxy.")
    if last_err:
        die(f"Figma API request failed: {last_err}")
    return {}  # unreachable


def _sleep_backoff(attempt: int, override: int | None = None) -> None:
    import time
    time.sleep(override if override is not None else min(2 ** attempt, 30))


def _node_document(data: dict, node_id: str) -> dict | None:
    nodes = data.get("nodes", {})
    if not nodes:
        return None
    first = nodes.get(node_id) or next(iter(nodes.values()))
    return first.get("document")


def fetch_shallow(file_key: str, node_id: str, token: str, depth: int) -> dict | None:
    """Fetch a node to a limited depth (never too large). Returns its document."""
    url = (f"{FIGMA_API}/files/{file_key}/nodes"
           f"?ids={urllib.parse.quote(node_id)}&depth={depth}")
    return _node_document(http_get_json(url, token), node_id)


def fetch_node_full(file_key: str, node_id: str, token: str) -> dict:
    """Fetch a single node's full subtree, auto-chunking if the API says it's too large."""
    url = f"{FIGMA_API}/files/{file_key}/nodes?ids={urllib.parse.quote(node_id)}"
    try:
        doc = _node_document(http_get_json(url, token), node_id)
        if doc is None:
            die(f"Node {node_id} not found in file {file_key}.")
        return doc
    except RequestTooLarge:
        # Fall back: get direct children shallowly, then fetch each child fully.
        print(f"  node {node_id} too large -- fetching its children individually ...")
        shallow = fetch_shallow(file_key, node_id, token, depth=1)
        if shallow is None:
            die(f"Could not fetch node {node_id} even shallowly.")
        kids = shallow.get("children", []) or []
        rebuilt: list[dict] = []
        for ch in kids:
            cid = ch.get("id")
            if not cid:
                rebuilt.append(ch)
                continue
            rebuilt.append(fetch_node_full(file_key, cid, token))
        shallow["children"] = rebuilt
        return shallow


def fetch_document(file_key: str, node_id: str | None, token: str) -> dict:
    """Return the root node document (subtree if node_id given, else whole file)."""
    if node_id:
        return fetch_node_full(file_key, node_id, token)
    data = http_get_json(f"{FIGMA_API}/files/{file_key}", token)
    doc = data.get("document")
    if not doc:
        die("No document in file response.")
    return doc


# --------------------------------------------------------------------------- #
# Color / effect / typography conversion
# --------------------------------------------------------------------------- #
def _chan(v: float) -> int:
    return max(0, min(255, round(v * 255)))


def color_to_css(color: dict, opacity: float | None = None) -> str:
    r, g, b = _chan(color.get("r", 0)), _chan(color.get("g", 0)), _chan(color.get("b", 0))
    a = color.get("a", 1.0)
    if opacity is not None:
        a *= opacity
    if a >= 0.999:
        return f"#{r:02X}{g:02X}{b:02X}"
    return f"rgba({r}, {g}, {b}, {round(a, 3)})"


def fills_to_css(fills: list) -> list[str]:
    out: list[str] = []
    for f in fills or []:
        if f.get("visible") is False:
            continue
        ftype = f.get("type")
        if ftype == "SOLID" and "color" in f:
            out.append(color_to_css(f["color"], f.get("opacity")))
        elif ftype and ftype.startswith("GRADIENT"):
            stops = f.get("gradientStops", [])
            parts = [color_to_css(s["color"]) for s in stops if "color" in s]
            if parts:
                kind = "linear-gradient" if "LINEAR" in ftype else "radial-gradient"
                out.append(f"{kind}({', '.join(parts)})")
    return out


def effects_to_css(effects: list) -> list[str]:
    out: list[str] = []
    for e in effects or []:
        if e.get("visible") is False:
            continue
        etype = e.get("type")
        if etype in ("DROP_SHADOW", "INNER_SHADOW"):
            off = e.get("offset", {})
            x, y = off.get("x", 0), off.get("y", 0)
            radius = e.get("radius", 0)
            spread = e.get("spread", 0)
            col = color_to_css(e.get("color", {}))
            inset = "inset " if etype == "INNER_SHADOW" else ""
            out.append(f"{inset}{x}px {y}px {radius}px {spread}px {col}")
    return out


def typography_of(node: dict) -> dict | None:
    style = node.get("style")
    if not style:
        return None
    return {
        "fontFamily": style.get("fontFamily"),
        "fontSize": style.get("fontSize"),
        "fontWeight": style.get("fontWeight"),
        "lineHeightPx": round(style.get("lineHeightPx", 0), 2) or None,
        "letterSpacing": style.get("letterSpacing"),
    }


# --------------------------------------------------------------------------- #
# Tree walking
# --------------------------------------------------------------------------- #
# Container types are traversed THROUGH to find screens inside them.
CONTAINER_TYPES = {"DOCUMENT", "CANVAS", "SECTION", "GROUP"}
# Screen types are collected AS screens (we do not descend past them for more screens).
COLLECT_TYPES = {"FRAME", "COMPONENT"}


def find_screens(root: dict) -> list[dict]:
    """Collect screen-like nodes (FRAME/COMPONENT), descending through containers.

    A FRAME/COMPONENT is treated as one screen and not descended into for more
    screens. CANVAS/SECTION/GROUP/DOCUMENT are traversed through. COMPONENT_SET is
    expanded into its variant COMPONENT children.
    """
    rtype = root.get("type")
    if rtype in COLLECT_TYPES:
        return [root]

    screens: list[dict] = []

    def descend(node: dict) -> None:
        ntype = node.get("type")
        if ntype in COLLECT_TYPES:
            screens.append(node)
            return
        if ntype == "COMPONENT_SET":
            for ch in node.get("children", []) or []:
                if ch.get("type") in COLLECT_TYPES:
                    screens.append(ch)
            return
        if ntype in CONTAINER_TYPES:
            for ch in node.get("children", []) or []:
                descend(ch)

    descend(root)
    if screens:
        return screens
    # Fallback: any direct children, else the root itself.
    kids = [n for n in root.get("children", []) or [] if n.get("type") in SCREEN_TYPES]
    return kids or [root]


def bbox_of(node: dict) -> dict | None:
    b = node.get("absoluteBoundingBox")
    if not b:
        return None
    return {
        "x": round(b.get("x", 0), 1),
        "y": round(b.get("y", 0), 1),
        "width": round(b.get("width", 0), 1),
        "height": round(b.get("height", 0), 1),
    }


def walk_collect(node: dict, acc: dict, depth: int = 0) -> None:
    """Recursively collect texts, colors, effects, fonts from a subtree."""
    ntype = node.get("type")

    for css in fills_to_css(node.get("fills", [])):
        acc["colors"].add(css)
    if node.get("strokes"):
        for css in fills_to_css(node.get("strokes", [])):
            acc["colors"].add(css)
    for sh in effects_to_css(node.get("effects", [])):
        acc["shadows"].add(sh)

    gap = node.get("itemSpacing")
    if isinstance(gap, (int, float)) and gap:
        acc["spacings"].add(round(gap, 1))
    for pk in ("paddingTop", "paddingRight", "paddingBottom", "paddingLeft"):
        pv = node.get(pk)
        if isinstance(pv, (int, float)) and pv:
            acc["spacings"].add(round(pv, 1))

    if ntype == "TEXT":
        chars = (node.get("characters") or "").strip()
        if chars:
            acc["texts"].append(chars)
        typo = typography_of(node)
        if typo and typo.get("fontSize"):
            acc["fonts"].add(json.dumps(typo, sort_keys=True))

    if ntype == "INSTANCE" and node.get("name"):
        acc["components"].add(node["name"])

    cr = node.get("cornerRadius")
    if isinstance(cr, (int, float)) and cr:
        acc["radii"].add(round(cr, 1))
    rr = node.get("rectangleCornerRadii")
    if isinstance(rr, list) and any(rr):
        acc["radii"].add("/".join(str(round(x, 1)) for x in rr))

    for child in node.get("children", []) or []:
        walk_collect(child, acc, depth + 1)


def child_layout_hint(node: dict) -> str:
    """Infer row/column/grid from immediate children coordinates."""
    kids = [c for c in node.get("children", []) or [] if c.get("absoluteBoundingBox")]
    if len(kids) < 2:
        return "single"
    xs = [c["absoluteBoundingBox"]["x"] for c in kids]
    ys = [c["absoluteBoundingBox"]["y"] for c in kids]
    x_spread = max(xs) - min(xs)
    y_spread = max(ys) - min(ys)
    # Figma also exposes layoutMode on auto-layout frames -- trust it if present.
    lm = node.get("layoutMode")
    if lm == "HORIZONTAL":
        return "row"
    if lm == "VERTICAL":
        return "column"
    if x_spread > 5 and y_spread > 5:
        return "grid"
    return "row" if x_spread >= y_spread else "column"


def autolayout_of(node: dict) -> dict | None:
    """Extract exact auto-layout spacing/padding/alignment from a Figma frame.

    Figma exposes these on any frame with auto-layout enabled; they are the exact
    values needed to reproduce spacing faithfully instead of guessing.
    """
    mode = node.get("layoutMode")
    if not mode or mode == "NONE":
        return None
    info: dict = {"direction": "row" if mode == "HORIZONTAL" else "column"}
    gap = node.get("itemSpacing")
    if isinstance(gap, (int, float)):
        info["gap"] = round(gap, 1)
    pads = {
        "top": node.get("paddingTop", 0) or 0,
        "right": node.get("paddingRight", 0) or 0,
        "bottom": node.get("paddingBottom", 0) or 0,
        "left": node.get("paddingLeft", 0) or 0,
    }
    if any(pads.values()):
        info["padding"] = {k: round(v, 1) for k, v in pads.items()}
    prim = node.get("primaryAxisAlignItems")
    if prim:
        info["justify"] = prim
    counter = node.get("counterAxisAlignItems")
    if counter:
        info["align"] = counter
    return info


def extract_screen(node: dict) -> dict:
    acc = {
        "texts": [],
        "colors": set(),
        "shadows": set(),
        "fonts": set(),
        "radii": set(),
        "spacings": set(),
        "components": set(),
    }
    walk_collect(node, acc)
    # de-dupe texts preserving order
    seen: set = set()
    texts: list[str] = []
    for t in acc["texts"]:
        if t not in seen:
            seen.add(t)
            texts.append(t)
    return {
        "id": node.get("id"),
        "name": node.get("name"),
        "type": node.get("type"),
        "bbox": bbox_of(node),
        "layoutHint": child_layout_hint(node),
        "layout": autolayout_of(node),
        "texts": texts,
        "colors": sorted(acc["colors"]),
        "shadows": sorted(acc["shadows"]),
        "radii": sorted(str(r) for r in acc["radii"]),
        "spacings": sorted(acc["spacings"]),
        "components": sorted(acc["components"]),
        "fonts": [json.loads(f) for f in sorted(acc["fonts"])],
    }


def build_spec(root: dict, file_key: str) -> dict:
    screens = find_screens(root)
    screen_specs = [extract_screen(s) for s in screens]

    palette: set = set()
    shadows: set = set()
    spacings: set = set()
    fonts: set = set()
    for s in screen_specs:
        palette.update(s["colors"])
        shadows.update(s["shadows"])
        spacings.update(s["spacings"])
        for f in s["fonts"]:
            fonts.add(json.dumps(f, sort_keys=True))

    return {
        "fileKey": file_key,
        "screenCount": len(screen_specs),
        "globalPalette": sorted(palette),
        "globalShadows": sorted(shadows),
        "globalSpacings": sorted(spacings),
        "globalFonts": [json.loads(f) for f in sorted(fonts)],
        "screens": screen_specs,
    }


# --------------------------------------------------------------------------- #
# Reference image download
# --------------------------------------------------------------------------- #
def download_images(file_key: str, screens: list[dict], token: str, out_dir: Path,
                    scale: int = 1) -> None:
    ref_dir = out_dir / "reference"
    ref_dir.mkdir(parents=True, exist_ok=True)
    ids = [s["id"] for s in screens if s.get("id")]
    if not ids:
        print("  (no screen ids to download)")
        return
    ids_param = urllib.parse.quote(",".join(ids))
    url = f"{FIGMA_API}/images/{file_key}?ids={ids_param}&format=png&scale={scale}"
    data = http_get_json(url, token)
    images = data.get("images", {})
    for s in screens:
        img_url = images.get(s["id"])
        if not img_url:
            continue
        safe = re.sub(r"[^A-Za-z0-9_-]+", "_", s.get("name") or s["id"]).strip("_")
        dest = ref_dir / f"{safe}.png"
        try:
            with urllib.request.urlopen(img_url, timeout=120) as resp:
                dest.write_bytes(resp.read())
            print(f"  saved {dest.name}")
        except Exception as e:  # noqa: BLE001
            print(f"  WARN: failed to download image for {s.get('name')}: {e}")


# --------------------------------------------------------------------------- #
# Markdown summary
# --------------------------------------------------------------------------- #
def spec_to_markdown(spec: dict) -> str:
    lines: list[str] = []
    lines.append(f"# Figma design spec ({spec['screenCount']} screen(s))\n")
    lines.append(f"File key: `{spec['fileKey']}`\n")

    lines.append("## Global color palette")
    for c in spec["globalPalette"]:
        lines.append(f"- `{c}`")
    lines.append("")

    if spec["globalShadows"]:
        lines.append("## Global shadow tokens")
        for s in spec["globalShadows"]:
            lines.append(f"- `{s}`")
        lines.append("")

    if spec.get("globalSpacings"):
        lines.append("## Global spacing scale (px)")
        lines.append("- " + ", ".join(f"`{s}`" for s in spec["globalSpacings"]))
        lines.append("")

    if spec["globalFonts"]:
        lines.append("## Typography")
        for f in spec["globalFonts"]:
            lines.append(
                f"- {f.get('fontFamily')} / {f.get('fontSize')}px / "
                f"weight {f.get('fontWeight')} / line-height {f.get('lineHeightPx')}px"
            )
        lines.append("")

    lines.append("## Screens\n")
    for i, s in enumerate(spec["screens"], 1):
        bbox = s.get("bbox") or {}
        size = f"{bbox.get('width')}x{bbox.get('height')}" if bbox else "unknown"
        lines.append(f"### {i}. {s.get('name')}  (`{s.get('id')}`)")
        lines.append(f"- type: {s.get('type')} | size: {size} | layout: {s.get('layoutHint')}")
        lay = s.get("layout")
        if lay:
            parts = [f"direction={lay.get('direction')}"]
            if "gap" in lay:
                parts.append(f"gap={lay['gap']}px")
            if "padding" in lay:
                p = lay["padding"]
                parts.append(
                    f"padding={p['top']}/{p['right']}/{p['bottom']}/{p['left']}px"
                )
            if "justify" in lay:
                parts.append(f"justify={lay['justify']}")
            if "align" in lay:
                parts.append(f"align={lay['align']}")
            lines.append(f"- auto-layout: {', '.join(parts)}")
        if s.get("spacings"):
            lines.append(f"- spacings: {', '.join('`'+str(x)+'px`' for x in s['spacings'])}")
        if s["colors"]:
            lines.append(f"- colors: {', '.join('`'+c+'`' for c in s['colors'][:24])}")
        if s["shadows"]:
            lines.append(f"- shadows: {', '.join('`'+x+'`' for x in s['shadows'][:8])}")
        if s["radii"]:
            lines.append(f"- radii: {', '.join('`'+r+'`' for r in s['radii'])}")
        if s["components"]:
            lines.append(f"- components: {', '.join(s['components'][:30])}")
        if s["texts"]:
            preview = " | ".join(s["texts"][:60])
            lines.append(f"- text: {preview}")
        lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    # Ensure progress lines appear immediately when stdout is not a TTY
    # (e.g. captured by Copilot / a pipe), otherwise Python block-buffers and the
    # run looks frozen during network waits.
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
        except Exception:
            pass
    p = argparse.ArgumentParser(description="Standalone Figma design extractor (stdlib only).")
    p.add_argument("--url", help="Figma file/design URL")
    p.add_argument("--file-key", help="Figma file key (alternative to --url)")
    p.add_argument("--node-id", help="Node id (e.g. 1:2). Optional with --file-key.")
    p.add_argument("--ids", help="Comma-separated node ids to extract (all are extracted; "
                   "overrides --node-id).")
    p.add_argument("--token", help="Figma PAT (else FIGMA_TOKEN / FIGMA_API_KEY / .env)")
    p.add_argument("--out", default="./.design-cache", help="Output directory")
    p.add_argument("--list", action="store_true",
                   help="Only enumerate screens (fast, shallow) -> figma_screens.md. "
                        "Use this first on large files, then re-run with --ids for specific screens.")
    p.add_argument("--list-depth", type=int, default=3,
                   help="Traversal depth for --list (default 3).")
    p.add_argument("--download-images", action="store_true",
                   help="Download one reference PNG per screen")
    p.add_argument("--scale", type=int, default=1, help="Reference PNG scale (1-4)")
    p.add_argument("--refresh", action="store_true",
                   help="Ignore any cached figma_raw.json in --out and re-fetch from the API. "
                        "By default a matching cache is reused to avoid rate limits.")
    p.add_argument("--from-json", help="Parse an existing raw JSON file instead of fetching")
    args = p.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---- Offline re-parse mode -------------------------------------------- #
    if args.from_json:
        raw = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
        # Accept either a raw /files response, a /nodes response, or a bare document.
        if "document" in raw:
            root = raw["document"]
            file_key = raw.get("name", "offline")
        elif "nodes" in raw:
            first = next(iter(raw["nodes"].values()))
            root = first.get("document", first)
            file_key = "offline"
        else:
            root = raw
            file_key = "offline"
        token = ""
    else:
        if args.url:
            file_key, node_id = parse_figma_url(args.url)
        elif args.file_key:
            file_key, node_id = args.file_key, (args.node_id or None)
            if node_id:
                node_id = node_id.replace("-", ":")
        else:
            die("Provide --url, or --file-key (with optional --node-id), or --from-json.")
            return

        node_ids: list[str] | None = None
        if args.ids:
            node_ids = [x.strip().replace("-", ":") for x in args.ids.split(",") if x.strip()]
            node_id = node_ids[0] if node_ids else None

        token = resolve_token(args.token)

        # ---- Fast list mode: enumerate screens shallowly, then stop ------- #
        if args.list:
            if not node_id:
                die("--list requires a node (URL with node-id, or --node-id/--ids).")
            print(f"Enumerating screens under {node_id} (depth={args.list_depth}) ...",
                  flush=True)
            print("  contacting Figma API (large pages can take 30-120s) ...", flush=True)
            shallow = fetch_shallow(file_key, node_id, token, depth=args.list_depth)
            if shallow is None:
                die(f"Could not fetch node {node_id}.")
            screens = find_screens(shallow)
            md = [f"# Figma screen inventory ({len(screens)} found)\n",
                  f"File key: `{file_key}`  |  Root node: `{node_id}`\n",
                  "Re-run with `--ids <id1,id2>` (or a URL node-id) to extract specific "
                  "screens in full.\n",
                  "| # | Name | Node id | Type | Size |",
                  "|---|------|---------|------|------|"]
            for i, s in enumerate(screens, 1):
                b = bbox_of(s) or {}
                size = f"{b.get('width')}x{b.get('height')}" if b else "?"
                name = (s.get("name") or "").replace("|", "\\|")
                md.append(f"| {i} | {name} | `{s.get('id')}` | {s.get('type')} | {size} |")
            (out_dir / "figma_screens.md").write_text("\n".join(md), encoding="utf-8")
            print(f"  inventory -> {out_dir / 'figma_screens.md'}  ({len(screens)} screens)")
            for s in screens[:60]:
                print(f"  - [{s.get('id')}] {s.get('name')}")
            if len(screens) > 60:
                print(f"  ... and {len(screens) - 60} more (see figma_screens.md)")
            return

        raw_path = out_dir / "figma_raw.json"
        meta_path = out_dir / "figma_raw.meta.json"
        cache_key = {"fileKey": file_key,
                     "nodes": node_ids or ([node_id] if node_id else [])}

        cached_meta = None
        if meta_path.exists():
            try:
                cached_meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                cached_meta = None

        if raw_path.exists() and not args.refresh and cached_meta == cache_key:
            print(f"  reusing cached {raw_path.name} (same file/node) -- no API call. "
                  "Pass --refresh to force a re-fetch.", flush=True)
            root = json.loads(raw_path.read_text(encoding="utf-8"))
        else:
            print(f"Fetching Figma document (file={file_key}, node={node_id or 'ALL'}) ...",
                  flush=True)
            if raw_path.exists() and not args.refresh and cached_meta is not None:
                print("  cached figma_raw.json is for a different file/node -- re-fetching.",
                      flush=True)
            if node_ids and len(node_ids) > 1:
                print(f"  extracting {len(node_ids)} nodes: {', '.join(node_ids)}")
                docs = [fetch_node_full(file_key, nid, token) for nid in node_ids]
                root = {"type": "CANVAS", "name": file_key, "children": docs}
            else:
                root = fetch_document(file_key, node_id, token)
            raw_path.write_text(json.dumps(root, ensure_ascii=False), encoding="utf-8")
            meta_path.write_text(json.dumps(cache_key), encoding="utf-8")
            print(f"  raw -> {raw_path}")

    print("Parsing design ...")
    spec = build_spec(root, file_key)

    (out_dir / "figma_spec.json").write_text(
        json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "figma_spec.md").write_text(spec_to_markdown(spec), encoding="utf-8")
    print(f"  spec -> {out_dir / 'figma_spec.json'}")
    print(f"  summary -> {out_dir / 'figma_spec.md'}")

    print(f"\nFound {spec['screenCount']} screen(s):")
    for s in spec["screens"]:
        print(f"  - [{s.get('id')}] {s.get('name')}  ({s.get('layoutHint')})")

    if args.download_images:
        if args.from_json or not token:
            print("Skipping image download (need a live token; not available in --from-json mode).")
        else:
            print("Downloading reference PNGs ...")
            download_images(file_key, spec["screens"], token, out_dir, args.scale)

    print("\nDone. Read figma_spec.md next -- do NOT hand-read figma_raw.json.")


if __name__ == "__main__":
    main()
