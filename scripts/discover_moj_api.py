"""Discover the MoJ legislation portal's underlying API via Playwright.

Why this exists:
  laws.moj.gov.sa is a Nuxt SPA. urllib/requests against any of its
  routes returns an empty shell. The actual API endpoints are called
  via XHR from the bundled JS, and the resource paths are obfuscated
  inside the minified bundle (we tried static grep — only generic UI
  routes were recoverable). The reliable way to find them is to launch
  a real browser and inspect the network panel. This script automates
  that.

Output:
  tests/fixtures/moj_api_samples/captures.json
    A single JSON file with one entry per captured request/response,
    keyed by capture phase ("listing_page_1", "listing_page_2",
    "detail", "pdf_download"). Each entry stores method, URL, request
    headers, request POST body (if any), response status, response
    headers, and the first 4 KB of the response body.

This runs once, in development, to inform the connector design. The
runtime connector (backend/app/connectors/moj.py) will use plain
httpx against the discovered endpoints — Playwright stays out of the
request path.

Usage:
  pip install -e 'backend[dev]'
  playwright install chromium
  python scripts/discover_moj_api.py
"""

from __future__ import annotations

import asyncio
import base64
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright


REPO = Path(__file__).resolve().parent.parent
OUT_DIR = REPO / "tests" / "fixtures" / "moj_api_samples"
OUT_FILE = OUT_DIR / "captures.json"

LISTING_URL = (
    "https://laws.moj.gov.sa/ar/legislations-regulations"
    "?pageNumber=1&pageSize=9&sortingBy=7"
)
PORTAL_HOSTS = {"laws.moj.gov.sa", "laws-gateway.moj.gov.sa"}
SKIP_RESOURCE_TYPES = {"image", "font", "stylesheet", "media", "manifest"}
SKIP_HOST_SUFFIXES = (
    ".google-analytics.com",
    ".googletagmanager.com",
    ".doubleclick.net",
    ".facebook.com",
    ".hotjar.com",
    "fonts.googleapis.com",
    "fonts.gstatic.com",
)
MAX_BODY_BYTES = 4096


def _should_skip(url: str, resource_type: str) -> bool:
    if resource_type in SKIP_RESOURCE_TYPES:
        return True
    host = urlparse(url).netloc
    if any(host.endswith(suffix) for suffix in SKIP_HOST_SUFFIXES):
        return True
    return False


def _make_recorder(captures: list[dict], phase: str):
    """Return (on_request, on_response) handlers that append to captures."""
    pending: dict[str, dict] = {}

    async def on_request(request):
        if _should_skip(request.url, request.resource_type):
            return
        try:
            post_data = request.post_data
        except Exception:  # noqa: BLE001
            post_data = None
        entry = {
            "phase": phase,
            "method": request.method,
            "url": request.url,
            "resource_type": request.resource_type,
            "request_headers": dict(request.headers),
            "request_post_data": post_data,
        }
        pending[id(request)] = entry

    async def on_response(response):
        request = response.request
        entry = pending.pop(id(request), None)
        if entry is None:
            return
        entry["response_status"] = response.status
        entry["response_status_text"] = response.status_text
        try:
            entry["response_headers"] = dict(response.headers)
        except Exception:  # noqa: BLE001
            entry["response_headers"] = {}
        try:
            body = await response.body()
            entry["response_body_bytes"] = len(body)
            sample = body[:MAX_BODY_BYTES]
            try:
                entry["response_body_sample"] = sample.decode("utf-8")
                entry["response_body_encoding"] = "utf-8"
            except UnicodeDecodeError:
                entry["response_body_sample"] = base64.b64encode(sample).decode("ascii")
                entry["response_body_encoding"] = "base64"
        except Exception as exc:  # noqa: BLE001
            entry["response_body_error"] = str(exc)
        captures.append(entry)

    return on_request, on_response


async def _wait_for_network_idle(page, *, timeout_ms: int = 8000) -> None:
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except Exception:
        # networkidle can flake on portals with long-polling pings; we
        # already captured what we needed.
        pass


async def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    captures: list[dict] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            locale="ar-SA",
            extra_http_headers={"Accept-Language": "ar,en;q=0.5"},
            user_agent=(
                "ETHKA-Suhaiman-KM/1.0 discovery "
                "(Mozilla/5.0 Chromium via Playwright)"
            ),
        )
        page = await context.new_page()

        # PHASE 1 — listing page (page 1)
        on_req, on_res = _make_recorder(captures, phase="listing_page_1")
        page.on("request", on_req)
        page.on("response", on_res)
        print("[phase] listing_page_1 →", LISTING_URL)
        await page.goto(LISTING_URL, wait_until="domcontentloaded", timeout=45_000)
        await _wait_for_network_idle(page)
        await page.wait_for_timeout(2000)

        # PHASE 2 — page 2 (rewrite query string, give it a moment to fetch)
        page.remove_listener("request", on_req)
        page.remove_listener("response", on_res)
        on_req, on_res = _make_recorder(captures, phase="listing_page_2")
        page.on("request", on_req)
        page.on("response", on_res)
        page2_url = LISTING_URL.replace("pageNumber=1", "pageNumber=2")
        print("[phase] listing_page_2 →", page2_url)
        await page.goto(page2_url, wait_until="domcontentloaded", timeout=45_000)
        await _wait_for_network_idle(page)
        await page.wait_for_timeout(2000)

        # PHASE 3 — pick the first legislation link rendered and follow it
        page.remove_listener("request", on_req)
        page.remove_listener("response", on_res)
        on_req, on_res = _make_recorder(captures, phase="detail")
        page.on("request", on_req)
        page.on("response", on_res)
        detail_href = await page.evaluate(
            """() => {
              const a = document.querySelector('a[href*="/legislation/"]');
              return a ? a.href : null;
            }"""
        )
        if detail_href:
            print("[phase] detail →", detail_href)
            await page.goto(detail_href, wait_until="domcontentloaded", timeout=45_000)
            await _wait_for_network_idle(page)
            await page.wait_for_timeout(2000)
        else:
            print("[phase] detail SKIPPED — no /legislation/ link in DOM")

        # PHASE 4 — attempt to capture a PDF request. The DOM usually
        # exposes a download anchor or button; we look for any anchor
        # pointing at a PDF or a file/download endpoint.
        page.remove_listener("request", on_req)
        page.remove_listener("response", on_res)
        on_req, on_res = _make_recorder(captures, phase="pdf_download")
        page.on("request", on_req)
        page.on("response", on_res)
        # Strategy: prefer clicking an actual element rather than
        # extracting an href and re-fetching, because the gateway's
        # validator may rely on something the click handler synthesises
        # (different param encoding, a fresh token, a POST, etc.). We
        # try clicks first, fall back to anchor href as a last resort.
        # Always dump every clickable element first, regardless of click
        # success — the previous run revealed "تصدير إلى PDF" is a
        # client-side export, not the source-PDF download. We need to
        # distinguish the two.
        all_clickables = await page.evaluate(
            """() => Array.from(document.querySelectorAll('a, button, [role=button]'))
              .map((el) => ({
                tag: el.tagName,
                text: (el.textContent || '').trim().slice(0, 80),
                aria: el.getAttribute('aria-label') || '',
                href: el.getAttribute('href') || '',
                cls: el.className || '',
              }))
              .filter((x) => x.text || x.href)"""
        )
        (OUT_DIR / "detail_page_buttons.json").write_text(
            json.dumps(all_clickables, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  dumped {len(all_clickables)} clickable elements to detail_page_buttons.json")

        # Look for an explicit "download original" / "نسخة أصلية" style
        # affordance — that should fire the server-side PDF endpoint.
        # "تصدير إلى PDF" is the client-side export and is excluded.
        clicked = await page.evaluate(
            """() => {
              const els = Array.from(document.querySelectorAll('a, button, [role=button]'));
              const reject = /تصدير/;  // export-to-pdf renders client-side
              const accept = /نسخة|أصلية|تنزيل|تحميل|الوثيقة|الأصلية|hard\\s*copy|word|pdfCopy|الأصلي/i;
              for (const c of els) {
                const text = (c.textContent || '').trim();
                const aria = (c.getAttribute('aria-label') || '').trim();
                const haystack = `${text} ${aria}`;
                if (reject.test(haystack)) continue;
                if (accept.test(haystack)) {
                  c.scrollIntoView();
                  c.click();
                  return haystack.slice(0, 120);
                }
              }
              return null;
            }"""
        )
        if clicked:
            print(f"[phase] pdf_download → clicked: {clicked!r}")
            # Let click handlers fire any XHR / nav and settle.
            await page.wait_for_timeout(4000)
            await _wait_for_network_idle(page, timeout_ms=10_000)
        else:
            print("[phase] pdf_download SKIPPED — no obvious download/PDF affordance in DOM")
            # As a last resort, dump all anchor/button text on the page
            # so the next run can hand-target it.
            dump = await page.evaluate(
                """() => Array.from(document.querySelectorAll('a, button'))
                  .map((el) => ({tag: el.tagName, text: (el.textContent || '').trim().slice(0, 80), href: el.getAttribute('href')}))
                  .filter((x) => x.text)"""
            )
            (OUT_DIR / "detail_page_buttons.json").write_text(
                json.dumps(dump, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"  dumped {len(dump)} clickable elements to detail_page_buttons.json")

        await browser.close()

    # Annotate the dump with a quick host-grouped index so the report
    # is easier to scan.
    by_host: dict[str, int] = {}
    for entry in captures:
        host = urlparse(entry["url"]).netloc
        by_host[host] = by_host.get(host, 0) + 1

    summary = {
        "captured_at_utc": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "listing_url": LISTING_URL,
        "total_entries": len(captures),
        "entries_by_host": by_host,
        "entries": captures,
    }
    OUT_FILE.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {len(captures)} entries to {OUT_FILE}")
    print("Hosts seen:")
    for host, count in sorted(by_host.items(), key=lambda kv: -kv[1]):
        marker = "★" if host in PORTAL_HOSTS else " "
        print(f"  {marker} {host}: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
