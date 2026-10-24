"""Exercise Next.js account and invitation flows against a local Django backend.
Creates disposable accounts/workspaces; run against a development database only.
"""
import os
import time
from playwright.sync_api import sync_playwright, expect

BASE = os.getenv('SNACK_URL', 'http://127.0.0.1:3000')
PASSWORD = 'Local-browser-account-password-2026'


def register(page, email):
    page.get_by_role('link', name='ساخت حساب تازه').click()
    page.locator('#id_first_name').fill('آزمایش مرورگر')
    page.locator('#id_username').fill(email)
    page.locator('#id_password').fill(PASSWORD)
    page.locator('#id_password2').fill(PASSWORD)
    page.get_by_role('button', name='ساخت حساب', exact=True).click()


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path=os.getenv('CHROME_PATH'))
    admin = browser.new_context(viewport={'width': 1440, 'height': 1000})
    page = admin.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    unique = str(time.time_ns())
    page.goto(BASE)
    expect(page.locator('#id_username')).to_be_visible()
    register(page, f'admin-{unique}@example.com')
    expect(page.locator('#workspace-name')).to_be_visible()
    page.locator('#workspace-name').fill('فضای آزمایش ' + unique)
    page.get_by_role('button', name='ساخت فضای کاری', exact=True).click()
    expect(page.locator('#channel-name')).to_have_text('general')
    expect(page.locator('#connection')).to_have_text('متصل')
    page.locator('#members-button').click()
    page.locator('#modal select').select_option('member')
    expect(page.locator('#toast')).to_contain_text('دست‌کم یک مدیر')
    page.locator('#close-modal').click()
    invited_email = f'invited-{unique}@example.com'
    page.locator('#invite-button').click()
    page.locator('#field-email').fill(invited_email)
    page.get_by_role('button', name='ارسال دعوت‌نامه', exact=True).click()
    link = page.locator('.invite-result')
    expect(link).to_be_visible(timeout=30000)
    invite_url = link.get_attribute('href')
    assert invite_url.startswith(BASE + '/invite/'), invite_url
    guest = browser.new_context()
    teammate = guest.new_page()
    teammate.on('pageerror', lambda error: errors.append(str(error)))
    teammate.goto(invite_url)
    expect(teammate.locator('#id_username')).to_be_visible()
    register(teammate, invited_email)
    expect(teammate.get_by_role('button', name='پذیرش دعوت‌نامه')).to_be_visible()
    teammate.get_by_role('button', name='پذیرش دعوت‌نامه').click()
    expect(teammate.locator('#channel-name')).to_have_text('general')
    expect(teammate.locator('#connection')).to_have_text('متصل')
    expect(teammate.locator('#invite-button')).to_be_hidden()
    teammate.locator('#message-input').fill('پیام عضو دعوت‌شده ' + unique)
    teammate.locator('#send-button').click()
    expect(page.locator('.message-body').filter(has_text='پیام عضو دعوت‌شده ' + unique)).to_be_visible()
    teammate.locator('#profile').click()
    expect(teammate.locator('#id_username')).to_be_visible()
    teammate.locator('#id_username').fill(invited_email)
    teammate.locator('#id_password').fill('wrong-password')
    teammate.get_by_role('button', name='ورود به اسنک').click()
    expect(teammate.get_by_role('alert')).to_be_visible()
    teammate.get_by_role('link', name='گذرواژه را فراموش کرده‌اید؟').click()
    teammate.locator('#id_username').fill(invited_email)
    teammate.get_by_role('button', name='ارسال پیوند بازنشانی').click()
    expect(teammate.get_by_role('status')).to_contain_text('پیوند بازنشانی', timeout=30000)
    # URL normalization must not turn an untrusted next parameter into an external redirect.
    teammate.goto(BASE + '/accounts/login/?next=%2F%0A%2Fexample.com')
    teammate.locator('#id_username').fill(invited_email)
    teammate.locator('#id_password').fill(PASSWORD)
    teammate.get_by_role('button', name='ورود به اسنک').click()
    expect(teammate.locator('#channel-name')).to_have_text('general')
    assert teammate.url.startswith(BASE + '/'), teammate.url
    assert not errors, errors
    browser.close()
    print('Account browser checks passed: signup, onboarding, last-admin guard, invitation through signup, member permissions, live delivery, logout, invalid login, password reset request, safe login redirects; no JS errors.')
