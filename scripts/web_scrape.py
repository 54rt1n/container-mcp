#!/usr/bin/env python3
"""Simple CLI to test web_scrape output (text or markdown)."""

import argparse
import asyncio
import json
from typing import Optional

from cmcp.managers.web_manager import WebManager


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test WebManager.scrape_webpage")
    parser.add_argument("url", help="URL to scrape")
    parser.add_argument(
        "--selector",
        help="CSS selector to target specific content",
        default=None,
    )
    parser.add_argument(
        "--output-format",
        help="Output format: text or markdown",
        default="text",
        choices=["text", "markdown", "md"],
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="Optional timeout in seconds",
    )
    return parser.parse_args()


async def run(url: str, selector: Optional[str], output_format: str, timeout: Optional[int]) -> int:
    manager = WebManager.from_env()
    result = await manager.scrape_webpage(
        url,
        selector=selector,
        output_format=output_format,
        timeout=timeout,
    )

    payload = {
        "success": result.success,
        "url": result.url,
        "title": result.title,
        "error": result.error,
        "content": result.content,
    }
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0 if result.success else 1


def main() -> int:
    args = parse_args()
    return asyncio.run(run(args.url, args.selector, args.output_format, args.timeout))


if __name__ == "__main__":
    raise SystemExit(main())
