"""Visual fixture + responsive checks for the selected Snack redesign.
Only screenshot data is intercepted; browser_smoke.py covers the real chat API.
"""
import copy
import json
import os
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from playwright.sync_api import sync_playwright, expect

BASE = os.getenv('SNACK_URL', 'http://127.0.0.1:3000')
ARTIFACTS = Path('artifacts')
ARTIFACTS.mkdir(exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path=os.getenv('CHROME_PATH'))
    page = browser.new_page(viewport={'width': 1440, 'height': 1024}, color_scheme='light')
    errors = []
    page.on('response', lambda response: print('HTTP error:', response.status, response.url) if response.status >= 400 else None)
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
    page.goto(BASE + '/accounts/login/')
    page.wait_for_load_state('networkidle')
    page.evaluate('document.fonts.ready')
    page.screenshot(path=str(ARTIFACTS / 'redesign-login-light.png'))
    page.locator('#id_username').fill(os.getenv('SNACK_ADMIN_USERNAME', 'admin'))
    page.locator('#id_password').fill(os.getenv('SNACK_ADMIN_PASSWORD', 'admin'))
    page.get_by_role('button', name='ورود به اسنک').click()
    expect(page.locator('#message-input')).to_be_enabled()
    session = page.evaluate("fetch('/api/session/').then(r => r.json())")
    workspace = session['workspaces'][0]['id']
    bootstrap = page.evaluate(f"fetch('/api/workspaces/{workspace}/').then(r => r.json())")
    general = next(channel for channel in bootstrap['channels'] if channel['name'] == 'general')
    history = page.evaluate(f"fetch('/api/channels/{general['id']}/messages/').then(r => r.json())")
    assert len(history['messages']) >= 4, 'Visual check requires demo message history'
    own = bootstrap['me']['id']
    others = [member for member in bootstrap['members'] if member['id'] != own]
    assert len(others) >= 2
    fixture = copy.deepcopy(bootstrap)
    fixture['channels'] = [channel for channel in fixture['channels'] if channel['name'] in ('general', 'design', 'engineering', 'random') or channel['kind'] == 'dm']
    order = {'general': 0, 'design': 1, 'engineering': 2, 'random': 3}
    fixture['channels'].sort(key=lambda channel: order.get(channel['name'], 4))
    for channel in fixture['channels']:
        channel['unread'] = 0
    fixture['members'] = fixture['members'][:3]
    messages = copy.deepcopy(history['messages'][:4])
    texts = [
        'سلام به همه!\nطرح اولیه آماده شد.\nخوشحال می‌شم نظرتون رو بدونم.',
        'عالیه!\nرنگ‌ها خیلی خوبه.\nدکمهٔ اصلی می‌تونه کمی بزرگ‌تر باشه.',
        'کاملاً موافقم.\nنسخهٔ جدید رو همین‌جا می‌فرستم.',
        'خیلی دوستش دارم!\nاین نسخه خواناتر و دوستانه‌تر شده.',
    ]
    for i, message in enumerate(messages):
        message.update(body=texts[i], sender_id=own if i in (0, 2) else others[0 if i == 1 else 1]['id'], sender=['Mina Farhadi', 'Omid Rahimi', 'Mina Farhadi', 'Sara Ahmadi'][i], deleted=False, edited_at=None, reply_to=None)
        message.pop('attachment', None)
    attachment = next((message['attachment'] for message in history['messages'] if message.get('attachment')), None)
    if attachment:
        messages[0]['attachment'] = {**attachment, 'name': 'login-design.png', 'size': 3481600}
    # Keep screenshot fixtures isolated from real messages sent by other test users.
    page.route_web_socket('**/ws/**', lambda socket: socket.send(json.dumps({'event': 'ready'})))
    page.route(re.compile(rf'/api/workspaces/{workspace}/$'), lambda route: route.fulfill(json=fixture))

    def visual_history(route):
        params = parse_qs(urlsplit(route.request.url).query)
        after = int(params.get('after', [0])[0])
        route.fulfill(json={'messages': [message for message in messages if message['id'] > after], 'has_more': False})

    page.route(re.compile(rf"/api/channels/{general['id']}/messages/(\?.*)?$"), visual_history)
    page.goto(BASE + f'/?workspace={workspace}')
    expect(page.locator('.message')).to_have_count(4)
    expect(page.locator('#connection')).to_have_text('متصل')
    page.evaluate('document.fonts.ready')
    page.locator('#message-scroll').evaluate('(el) => { el.scrollTop = 0; }')
    page.mouse.move(4, 80)
    assert page.locator('.rail').count() == 0
    assert page.locator('.sidebar').bounding_box()['x'] > page.locator('.main').bounding_box()['x']
    assert page.locator('.message-own').first.bounding_box()['x'] > page.locator('.message-other').first.bounding_box()['x']
    assert page.evaluate('document.fonts.check("800 16px IRANYekanXFaNum")')
    last = page.locator('.message-bubble').last.bounding_box()
    scroll = page.locator('#message-scroll').bounding_box()
    assert last['y'] + last['height'] <= scroll['y'] + scroll['height'] + 1, 'Reference messages clipped above composer'
    page.screenshot(path=str(ARTIFACTS / 'redesign-implementation-light.png'))
    for width, height in [(1024, 768), (768, 1024), (720, 900), (390, 844), (320, 740)]:
        page.set_viewport_size({'width': width, 'height': height})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'Overflow at {width}'
        compose = page.locator('#compose').bounding_box()
        assert compose['y'] + compose['height'] <= height, f'Composer clipped at {width}'
        button = page.locator('.theme-toggle').bounding_box()
        search = page.locator('#search-form').bounding_box()
        assert button['x'] + button['width'] <= search['x'], f'Theme/search overlap at {width}'
        if width <= 720:
            expect(page.locator('#sidebar')).not_to_be_visible()
            page.locator('#mobile-menu').click()
            expect(page.locator('#sidebar')).to_be_visible()
            expect(page.locator('#close-sidebar')).to_be_focused()
            page.keyboard.press('Escape')
            expect(page.locator('#sidebar')).not_to_be_visible()
            expect(page.locator('#mobile-menu')).to_be_focused()
            page.locator('#mobile-menu').click()
            page.locator('.sidebar-backdrop').click(position={'x': 8, 'y': 200})
            expect(page.locator('#sidebar')).not_to_be_visible()
            page.locator('#mobile-menu').click()
            page.locator('#close-sidebar').click()
            expect(page.locator('#sidebar')).not_to_be_visible()
        if width == 390:
            page.locator('#mobile-menu').blur()
            page.screenshot(path=str(ARTIFACTS / 'redesign-implementation-mobile.png'))
    page.set_viewport_size({'width': 1440, 'height': 1024})
    page.get_by_role('button', name='حالت تیره', exact=True).click()
    expect(page.locator('html')).to_have_attribute('data-theme', 'dark')
    page.wait_for_function("getComputedStyle(document.querySelector('.dashboard-tile.active')).backgroundColor === 'rgb(48, 44, 76)'")
    page.locator('#message-scroll').evaluate('(el) => { el.scrollTop = 0; }')
    page.screenshot(path=str(ARTIFACTS / 'redesign-implementation-dark.png'))
    page.locator('#add-channel').click()
    expect(page.locator('#modal')).to_be_visible()
    page.screenshot(path=str(ARTIFACTS / 'redesign-dialog-dark.png'))
    page.locator('#close-modal').click()
    assert not errors, errors
    browser.close()
print('Redesign checks passed: alternating bubbles, unified sidebar, fonts, five responsive widths, drawer keyboard controls, dark theme/dialog; no console or JS errors. Screenshot content uses a visual-only fixture.')
