"""Check Lucide icons and their controls against the running app."""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

BASE = os.getenv('SNACK_URL', 'http://127.0.0.1:3000')
Path('artifacts').mkdir(exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path=os.getenv('CHROME_PATH'))
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(BASE + '/accounts/login/')
    expect(page.locator('.brand svg.lucide').first).to_be_visible()
    expect(page.locator('.theme-toggle svg.lucide')).to_be_visible()
    page.locator('#id_username').fill(os.getenv('SNACK_ADMIN_USERNAME', 'admin'))
    page.locator('#id_password').fill(os.getenv('SNACK_ADMIN_PASSWORD', 'admin'))
    page.get_by_role('button', name='ورود به اسنک').click()
    expect(page.locator('#message-input')).to_be_enabled()
    for selector in ['.brand-mark', '#home-button', '#activity-button', '#workspace-button', '#add-channel', '#add-dm', '#invite-button', '#channel-members', '#channel-symbol', '#attach-button', '#emoji-button', '#send-button', '#search-form', '.theme-toggle']:
        icon = page.locator(selector + ' svg.lucide').first
        expect(icon).to_be_visible()
        assert icon.get_attribute('aria-hidden') == 'true', selector
        assert page.locator(selector).inner_text().strip() not in ['＋', '↑', '☺', '☀', '☾', '⌂', '♧']
    expect(page.locator('#attach-button svg.lucide-paperclip')).to_be_visible()
    page.locator('#add-channel').click()
    expect(page.locator('#close-modal svg.lucide')).to_be_visible()
    page.locator('#close-modal').click()
    page.get_by_role('button', name='متن ضخیم', exact=True).click()
    expect(page.locator('#message-input')).to_have_value('****')
    page.locator('#message-input').fill('')
    page.locator('#emoji-button').click()
    expect(page.locator('#modal')).to_be_visible()
    page.locator('#close-modal').click()
    page.screenshot(path='artifacts/icons-light-desktop.png')
    page.get_by_role('button', name='حالت تیره', exact=True).click()
    expect(page.locator('html')).to_have_attribute('data-theme', 'dark')
    page.screenshot(path='artifacts/icons-dark-desktop.png')
    page.set_viewport_size({'width': 390, 'height': 844})
    expect(page.locator('#mobile-menu svg.lucide')).to_be_visible()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.locator('#mobile-menu').click()
    expect(page.locator('#sidebar')).to_be_visible()
    page.locator('#channels .channel-row').first.click()
    expect(page.locator('#sidebar')).not_to_have_class('sidebar open')
    page.screenshot(path='artifacts/icons-dark-mobile.png')
    assert not errors, errors
    browser.close()
print('Icon browser checks passed: real SVG icons, accessible controls, formatting, emoji dialog, theme toggle, desktop/mobile layout; no JS errors.')
