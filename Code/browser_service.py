"""
OpenClaw Browser Service - Phase 21
Browser automation using Playwright for web access and interactions.
"""

from playwright.async_api import async_playwright, Browser, Page
from typing import Optional, List, Dict, Any
import asyncio
import base64
import json


class BrowserTool:
    def __init__(self):
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.is_initialized = False

    async def init(self, headless: bool = True):
        """Initialize the browser"""
        if self.is_initialized:
            return

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=headless)
        self.page = await self.browser.new_page()
        self.is_initialized = True

    async def navigate(self, url: str) -> Dict[str, Any]:
        """Navigate to a URL"""
        if not self.is_initialized:
            await self.init()

        try:
            response = await self.page.goto(url, wait_until="domcontentloaded")
            title = await self.page.title()
            url_current = self.page.url

            return {
                "success": True,
                "title": title,
                "url": url_current,
                "status": response.status if response else None,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def click(self, selector: str) -> Dict[str, Any]:
        """Click on an element"""
        try:
            await self.page.click(selector)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def type(
        self, selector: str, text: str, clear: bool = True
    ) -> Dict[str, Any]:
        """Type text into an element"""
        try:
            if clear:
                await self.page.fill(selector, "")
            await self.page.fill(selector, text)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def press(self, selector: str, key: str) -> Dict[str, Any]:
        """Press a key on an element"""
        try:
            await self.page.press(selector, key)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def wait_for_selector(
        self, selector: str, timeout: int = 30000
    ) -> Dict[str, Any]:
        """Wait for selector to appear"""
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def wait_forNavigation(
        self, url_pattern: str = None, timeout: int = 30000
    ) -> Dict[str, Any]:
        """Wait for navigation"""
        try:
            if url_pattern:
                await self.page.wait_for_url(url_pattern, timeout=timeout)
            else:
                await self.page.wait_for_load_state("networkidle", timeout=timeout)
            return {"success": True, "url": self.page.url}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def screenshot(self, full_page: bool = False) -> Dict[str, Any]:
        """Take a screenshot"""
        try:
            if not self.is_initialized:
                return {"success": False, "error": "Browser not initialized"}

            img_bytes = await self.page.screenshot(full_page=full_page)
            img_base64 = base64.b64encode(img_bytes).decode()

            return {"success": True, "screenshot": img_base64, "format": "base64"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_html(self) -> Dict[str, Any]:
        """Get page HTML"""
        try:
            html = await self.page.content()
            return {"success": True, "html": html}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def extract_text(self, selector: str) -> Dict[str, Any]:
        """Extract text from element"""
        try:
            element = await self.page.query_selector(selector)
            if not element:
                return {"success": False, "error": "Element not found"}

            text = await element.inner_text()
            return {"success": True, "text": text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def extract_all(self, selector: str) -> Dict[str, Any]:
        """Extract all matching elements"""
        try:
            elements = await self.page.query_selector_all(selector)
            results = []

            for el in elements:
                text = await el.inner_text()
                html = await el.inner_html()
                tag = await el.evaluate("el => el.tagName")

                results.append({"tag": tag, "text": text.strip(), "html": html})

            return {"success": True, "count": len(results), "elements": results}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def evaluate(self, js: str) -> Dict[str, Any]:
        """Evaluate JavaScript"""
        try:
            result = await self.page.evaluate(js)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_links(self) -> Dict[str, Any]:
        """Get all links on page"""
        try:
            links = await self.page.eval_on_selector_all(
                "a[href]",
                "els => els.map(el => ({text: el.text content, href: el.href}))",
            )
            return {"success": True, "links": links}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def scroll_down(self, pixels: int = 500) -> Dict[str, Any]:
        """Scroll down"""
        try:
            await self.page.evaluate(f"window.scrollBy(0, {pixels})")
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def scroll_to_bottom(self) -> Dict[str, Any]:
        """Scroll to bottom of page"""
        try:
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def go_back(self) -> Dict[str, Any]:
        """Go back in history"""
        try:
            await self.page.go_back()
            return {"success": True, "url": self.page.url}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def go_forward(self) -> Dict[str, Any]:
        """Go forward in history"""
        try:
            await self.page.go_forward()
            return {"success": True, "url": self.page.url}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def reload(self) -> Dict[str, Any]:
        """Reload page"""
        try:
            await self.page.reload()
            return {"success": True, "url": self.page.url}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def close(self):
        """Close browser"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

        self.is_initialized = False
        self.browser = None
        self.page = None
        self.playwright = None

    async def get_cookies(self) -> Dict[str, Any]:
        """Get all cookies"""
        try:
            cookies = await self.page.context.cookies()
            return {"success": True, "cookies": cookies}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def set_cookies(self, cookies: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Set cookies"""
        try:
            await self.page.context.add_cookies(cookies)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}


browser_tool = BrowserTool()
