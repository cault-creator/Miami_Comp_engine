"""Local Playwright browser helper for Miami-Dade public-records sites."""
from pathlib import Path

from playwright.async_api import async_playwright


class BrowserSession:
    def __init__(self, context, playwright):
        self.context = context
        self.playwright = playwright
        self.page = None

    async def new_page(self):
        self.page = await self.context.new_page()
        return self.page

    async def goto(self, url, **kwargs):
        if self.page is None:
            await self.new_page()
        return await self.page.goto(url, **kwargs)

    async def close(self):
        await self.context.close()
        await self.playwright.stop()


async def get_browser(profile, timeout_seconds=300, headless=False):
    """Return a browser session compatible with the original toolkit scripts."""
    playwright = await async_playwright().start()
    profile_dir = Path("browser-profiles") / profile
    profile_dir.mkdir(parents=True, exist_ok=True)
    context = await playwright.chromium.launch_persistent_context(
        user_data_dir=str(profile_dir),
        headless=headless,
        args=["--disable-blink-features=AutomationControlled"],
    )
    context.set_default_timeout(timeout_seconds * 1000)
    session = BrowserSession(context, playwright)
    await session.new_page()
    return session
