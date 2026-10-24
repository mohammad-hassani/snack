"""Verify theme preference, contrast, and layout against the running Next.js app."""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

BASE = os.getenv('SNACK_URL', 'http://127.0.0.1:3000')
ARTIFACTS = Path('artifacts')
ARTIFACTS.mkdir(exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path=os.getenv('CHROME_PATH'))
    context = browser.new_context(color_scheme='dark', viewport={'width': 1440, 'height': 1000})
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(BASE + '/accounts/login/')
    expect(page.locator('html')).to_have_attribute('data-theme', 'dark')
    toggle = page.get_by_role('button', name='حالت تیره', exact=True)
    expect(toggle).to_have_attribute('aria-pressed', 'true')
    assert page.locator('body').evaluate('(el) => getComputedStyle(el).backgroundColor') == 'rgb(24, 30, 44)'
    page.screenshot(path=str(ARTIFACTS / 'theme-dark-login.png'))
    toggle.focus()
    page.keyboard.press('Enter')
    expect(page.locator('html')).to_have_attribute('data-theme', 'light')
    assert page.evaluate('localStorage.getItem("snack-theme")') == 'light'
    page.reload()
    expect(page.locator('html')).to_have_attribute('data-theme', 'light')
    # Login navigation must retain the saved theme.
    page.locator('#id_username').fill(os.getenv('SNACK_ADMIN_USERNAME', 'admin'))
    page.locator('#id_password').fill(os.getenv('SNACK_ADMIN_PASSWORD', 'admin'))
    page.get_by_role('button', name='ورود به اسنک').click()
    expect(page.locator('#channel-name')).to_be_visible()
    expect(page.locator('html')).to_have_attribute('data-theme', 'light')
    toggle.click()
    expect(page.locator('html')).to_have_attribute('data-theme', 'dark')
    assert page.locator('.main').evaluate('(el) => getComputedStyle(el).backgroundColor') == 'rgb(24, 30, 44)'
    assert page.locator('#message-input').evaluate('(el) => getComputedStyle(el).color') == 'rgb(229, 233, 243)'
    page.locator('#search').fill('Morning')
    page.locator('#search-form').evaluate('(form) => form.requestSubmit()')
    expect(page.locator('#search-results')).to_be_visible()
    assert page.locator('#search-results').evaluate('(el) => getComputedStyle(el).backgroundColor') == 'rgb(24, 30, 44)'
    page.locator('#close-search').click()
    page.locator('#add-channel').click()
    expect(page.locator('#modal')).to_be_visible()
    assert page.locator('#modal').evaluate('(el) => getComputedStyle(el).backgroundColor') == 'rgb(36, 45, 64)'
    page.locator('#close-modal').click()
    page.screenshot(path=str(ARTIFACTS / 'theme-dark-workspace.png'))
    page.set_viewport_size({'width': 390, 'height': 844})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    button_box = toggle.bounding_box()
    search_box = page.locator('#search-form').bounding_box()
    assert button_box['x'] + button_box['width'] <= search_box['x'], 'Theme toggle overlaps search'
    page.screenshot(path=str(ARTIFACTS / 'theme-dark-mobile.png'))
    page.reload()
    expect(page.locator('html')).to_have_attribute('data-theme', 'dark')
    # An explicit dark choice overrides a light operating-system preference.
    page.emulate_media(color_scheme='light')
    page.reload()
    expect(page.locator('html')).to_have_attribute('data-theme', 'dark')
    # Storage restrictions must not prevent theme selection.
    blocked = browser.new_context(color_scheme='dark')
    blocked.add_init_script("Object.defineProperty(window, 'localStorage', { get() { throw new Error('blocked'); } });")
    other = blocked.new_page()
    other.on('pageerror', lambda error: errors.append(str(error)))
    other.goto(BASE + '/accounts/login/')
    expect(other.locator('html')).to_have_attribute('data-theme', 'dark')
    other.get_by_role('button', name='حالت تیره', exact=True).click()
    expect(other.locator('html')).to_have_attribute('data-theme', 'light')
    assert not errors, errors
    browser.close()
    print('Theme browser checks passed: system default, keyboard toggle, saved preference, reload/navigation, dark chat/dialog, mobile layout, blocked storage; no JS errors.')
