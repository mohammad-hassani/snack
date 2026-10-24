"""Verify composer formatting and safe rendering through real Django/WebSockets."""
import os
import time
from playwright.sync_api import sync_playwright, expect

BASE = os.getenv('SNACK_URL', 'http://127.0.0.1:3000')
unique = str(time.time_ns())


def sign_in(page, username, password):
    page.goto(BASE + '/accounts/login/')
    page.locator('#id_username').fill(username)
    page.locator('#id_password').fill(password)
    page.get_by_role('button', name='ورود به اسنک').click()
    expect(page.locator('#message-input')).to_be_enabled()
    page.locator('#channels .channel-row').filter(has_text='general').click()
    expect(page.locator('#connection')).to_have_text('متصل')


def select_text(page, word):
    page.locator('#message-input').evaluate('(el, word) => { const start = el.value.indexOf(word); el.focus(); el.setSelectionRange(start, start + word.length); }', word)


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path=os.getenv('CHROME_PATH'))
    page = browser.new_page(viewport={'width': 1440, 'height': 1024})
    other = browser.new_page(viewport={'width': 1280, 'height': 900})
    errors = []
    for tab in (page, other):
        tab.on('pageerror', lambda error: errors.append(str(error)))
    sign_in(page, os.getenv('SNACK_ADMIN_USERNAME', 'admin'), os.getenv('SNACK_ADMIN_PASSWORD', 'admin'))
    sign_in(other, 'omid@snack.local', os.getenv('SNACK_DEMO_PASSWORD', 'Local-smoke-password-2026'))
    area = page.locator('#message-input')
    area.fill('')
    page.get_by_role('button', name='متن ضخیم', exact=True).click()
    area.press_sequentially('bold')
    expect(area).to_have_value('**bold**')
    area.fill('bold italic code ' + unique)
    for word, button in [('bold', 'متن ضخیم'), ('italic', 'متن مورب'), ('code', 'کد')]:
        select_text(page, word)
        page.get_by_role('button', name=button, exact=True).click()
    expect(area).to_have_value('**bold** _italic_ `code` ' + unique)
    page.locator('#send-button').click()
    message = page.locator('.message').filter(has=page.locator('.message-body').filter(has_text=unique))
    expect(message.locator('strong')).to_have_text('bold')
    expect(message.locator('em')).to_have_text('italic')
    expect(message.locator('code')).to_have_text('code')
    assert message.locator('strong').evaluate('(el) => getComputedStyle(el).fontWeight') == '800'
    assert message.locator('em').evaluate('(el) => getComputedStyle(el).fontStyle') == 'italic'
    incoming = other.locator('.message').filter(has=other.locator('.message-body').filter(has_text=unique))
    expect(incoming.locator('strong')).to_have_text('bold')
    message_id = message.get_attribute('id')
    # The same renderer must work after edits, reload, search, and reply previews.
    message.hover()
    message.get_by_role('button', name='ویرایش', exact=True).click()
    page.locator('#modal textarea').fill('**updated** _edited_ `fixed` ' + unique)
    page.get_by_role('button', name='ذخیرهٔ تغییرات').click()
    expect(incoming.locator('strong')).to_have_text('updated')
    page.reload()
    expect(page.locator(f'#{message_id} strong')).to_have_text('updated')
    page.locator('#search').fill(unique)
    page.locator('#search-form').evaluate('(el) => el.requestSubmit()')
    expect(page.locator('.result strong')).to_have_text('updated')
    page.locator('#close-search').click()
    page.locator(f'#{message_id}').hover()
    page.locator(f'#{message_id}').get_by_role('button', name='پاسخ', exact=True).click()
    expect(page.locator('#reply-banner strong')).to_have_text('updated')
    area.fill('reply ' + unique)
    page.locator('#send-button').click()
    reply_message = page.locator('.message').filter(has=page.locator('.message-body').filter(has_text='reply ' + unique))
    reply_message.get_by_role('button', name='رفتن به پیام اصلی').click()
    expect(page.locator(f'#{message_id}')).to_be_focused()
    # Hide the original from the initial page to exercise older-history navigation.
    original = None
    def history(route):
        global original
        if 'after=' in route.request.url:
            route.continue_()
            return
        response = route.fetch()
        payload = response.json()
        if 'before=' in route.request.url:
            route.fulfill(json={'messages': [original], 'has_more': False})
        else:
            original = next((item for item in payload['messages'] if 'message-' + str(item['id']) == message_id), original)
            payload['messages'] = [item for item in payload['messages'] if item['id'] != original['id']]
            payload['has_more'] = True
            route.fulfill(json=payload)
    page.route('**/api/channels/*/messages/?*', history)
    page.route('**/api/channels/*/messages/', history)
    page.reload()
    expect(page.locator(f'#{message_id}')).to_have_count(0)
    reply_message.get_by_role('button', name='رفتن به پیام اصلی').focus()
    page.keyboard.press('Enter')
    expect(page.locator(f'#{message_id}')).to_be_focused()
    page.unroute('**/api/channels/*/messages/?*', history)
    page.unroute('**/api/channels/*/messages/', history)
    code = 'const value = "' + unique + '";\n' + 'console.log(value);'
    area.fill(code)
    area.evaluate('(el) => el.select()')
    page.get_by_role('button', name='کد', exact=True).click()
    expect(area).to_have_value('```\n' + code + '\n```')
    page.locator('#send-button').click()
    block = page.locator('code.code-block').filter(has_text=unique)
    expect(block).to_have_text(code)
    expect(other.locator('code.code-block').filter(has_text=unique)).to_have_text(code)
    assert block.get_attribute('dir') == 'ltr'
    safety = '**safe** <img src=x onerror="window.snackUnsafe=true"> `**literal**` ' + unique
    area.fill(safety)
    page.locator('#send-button').click()
    safe = page.locator('.message').filter(has=page.locator('.message-body').filter(has_text='<img src=x')).filter(has_text=unique)
    expect(safe.locator('strong')).to_have_text('safe')
    expect(safe.locator('code')).to_have_text('**literal**')
    assert safe.locator('img,script').count() == 0
    assert not page.evaluate('Boolean(window.snackUnsafe)')
    area.fill('x' * 3999)
    page.get_by_role('button', name='متن ضخیم', exact=True).click()
    expect(area).to_have_value('x' * 3999)
    expect(page.locator('#toast')).to_contain_text('۴۰۰۰')
    area.fill('')
    page.set_viewport_size({'width': 320, 'height': 740})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert not errors, errors
    browser.close()
print('Formatting browser checks passed: toolbar selection/caret, real two-user styled delivery, edit/reload/search/reply, reply navigation by mouse/keyboard including unloaded originals, multiline code, HTML safety, length limit, mobile fit; no JS errors.')
