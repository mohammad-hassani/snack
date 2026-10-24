"""Run against a development server after seed_demo --password "$SNACK_DEMO_PASSWORD"."""
import os
import re
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

BASE = os.getenv('SNACK_URL', 'http://127.0.0.1:3000')
PASSWORD = os.environ['SNACK_DEMO_PASSWORD']
ARTIFACTS = Path('artifacts')
ARTIFACTS.mkdir(exist_ok=True)


def sign_in(page, email):
    page.goto(BASE)
    page.wait_for_load_state('networkidle')
    page.locator('#id_username').fill(email)
    page.locator('#id_password').fill(PASSWORD)
    page.locator('form button.primary').click()
    expect(page.locator('#channel-name')).to_have_text('general')
    expect(page.locator('#connection')).to_have_text('متصل')
    expect(page.locator('#member-count')).to_have_text(re.compile(r'^[۰-۹]+$'))


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path=os.getenv('CHROME_PATH'))
    context = browser.new_context(viewport={'width': 1440, 'height': 1024})
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    sign_in(page, 'mina@snack.local')
    page.screenshot(path=str(ARTIFACTS / 'workspace-desktop.png'), full_page=True)
    second = browser.new_context(viewport={'width': 1280, 'height': 900})
    teammate = second.new_page()
    teammate.on('pageerror', lambda error: errors.append(str(error)))
    sign_in(teammate, 'omid@snack.local')
    assert page.locator('html').get_attribute('lang') == 'fa'
    assert page.locator('html').get_attribute('dir') == 'rtl'
    rail, sidebar, main = [page.locator(selector).bounding_box() for selector in ['.rail', '.sidebar', '.main']]
    assert rail['x'] > sidebar['x'] > main['x'], 'Desktop navigation is not mirrored'
    unique = f'آزمایش فارسی {time.time_ns()} — API v2 و نسخهٔ ۱۲۳'
    page.locator('#message-input').fill(unique)
    page.locator('#send-button').click()
    expect(page.locator('.message-body').filter(has_text=unique)).to_be_visible()
    expect(teammate.locator('.message-body').filter(has_text=unique)).to_be_visible()
    message = page.locator('.message').filter(has=page.locator('.message-body').filter(has_text=unique))
    message_id = message.get_attribute('id')
    message = page.locator(f'#{message_id}')
    message.hover()
    message.get_by_role('button', name='ویرایش', exact=True).click()
    page.locator('#modal textarea').fill(unique + ' edited')
    page.get_by_role('button', name='ذخیرهٔ تغییرات', exact=True).click()
    expect(teammate.locator('.message-body').filter(has_text=unique + ' edited')).to_be_visible()
    # Reconnect recovery after missing an incoming message.
    second.set_offline(True)
    missed = unique + ' after reconnect'
    page.locator('#message-input').fill(missed)
    page.locator('#send-button').click()
    expect(page.locator('.message-body').filter(has_text=missed)).to_be_visible()
    second.set_offline(False)
    expect(teammate.locator('.message-body').filter(has_text=missed)).to_be_visible(timeout=25000)
    # Reply, file upload, and search use the actual backend.
    message.hover()
    message.get_by_role('button', name='پاسخ', exact=True).click()
    page.locator('#message-input').fill('Reply from browser check')
    page.locator('#send-button').click()
    expect(page.locator('.reply-ref').filter(has_text=unique)).to_be_visible()
    page.locator('#attachment').set_input_files({'name': 'smoke-notes.txt', 'mimeType': 'text/plain', 'buffer': b'Browser attachment check'})
    page.locator('#send-button').click()
    expect(page.get_by_role('link', name='smoke-notes.txt', exact=False).last).to_be_visible()
    page.locator('#search').fill(unique)
    page.locator('#search-form').evaluate('(form) => form.requestSubmit()')
    expect(page.locator('.result').first).to_be_visible()
    page.locator('#close-search').click()
    # A newly created private channel never appears in the other account.
    channel_name = f'private-smoke-{time.time_ns()}'
    page.locator('#add-channel').click()
    page.locator('#field-name').fill(channel_name)
    page.locator('#channel-kind').select_option('private')
    page.locator('#modal').get_by_role('button', name='ساخت کانال', exact=True).click()
    expect(page.locator('#channel-name')).to_have_text(channel_name)
    teammate.reload()
    expect(teammate.locator('#connection')).to_have_text('متصل')
    expect(teammate.locator('#channels')).not_to_contain_text(channel_name)
    # Start a DM from the member picker.
    page.locator('#add-dm').click()
    page.locator('#modal .person').filter(has_text='omid@snack.local').click()
    expect(page.locator('#channel-name')).not_to_have_text(channel_name)
    page.locator('#channels .channel-row').filter(has_text='general').click()
    expect(page.locator('#channel-name')).to_have_text('general')
    message = page.locator(f'#{message_id}')
    message.hover()
    message.get_by_role('button', name='حذف', exact=True).click()
    page.locator('#modal').get_by_role('button', name='حذف پیام', exact=True).click()
    expect(page.locator('.message-body.deleted').first).to_be_visible()
    page.reload()
    expect(page.locator('#connection')).to_have_text('متصل')
    expect(page.locator('.message-body').filter(has_text=missed)).to_be_visible()
    page.set_viewport_size({'width': 390, 'height': 844})
    page.screenshot(path=str(ARTIFACTS / 'workspace-mobile.png'), full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Mobile overflow'
    assert page.locator('#compose').bounding_box()['y'] + page.locator('#compose').bounding_box()['height'] <= 844, 'Composer outside mobile viewport'
    page.locator('#mobile-menu').click()
    expect(page.locator('#sidebar')).to_be_visible()
    assert page.locator('#sidebar').bounding_box()['x'] > 0, 'Mobile drawer should open from the right'
    assert page.locator('#sidebar').bounding_box()['x'] + page.locator('#sidebar').bounding_box()['width'] <= page.locator('.rail').bounding_box()['x'] + 1
    assert not errors, errors
    browser.close()
    print('Browser smoke passed: live delivery, edit/delete, replies, uploads, search, reconnect, private channel, DM, reload, mobile; no JS errors.')
