'use strict';
const $ = (selector) => document.querySelector(selector);
const app = $('#app');
const workspace = app.dataset.workspace;
const csrf = document.querySelector('[name=csrfmiddlewaretoken]').value;
const state = { me: null, channels: [], members: [], current: null, messages: new Map(), socket: null, reply: null, hasMore: false, activeRequest: 0, reconnect: 1000, loading: false };
let toastTimer, typingTimer, lastTyping = 0, refreshTimer;
const number = new Intl.NumberFormat('fa-IR');
const roleLabels = { member: 'عضو', admin: 'مدیر' };
const colors = ['lavender', 'mint', 'peach', 'blue', 'rose'];
function el(tag, className, text) { const node = document.createElement(tag); if (className) node.className = className; if (text !== undefined) node.textContent = text; if (['input', 'textarea'].includes(tag)) node.dir = 'auto'; return node; }
function avatar(name, id, small = false) { return el('span', `avatar ${colors[Number(id) % colors.length]}${small ? ' small-avatar' : ''}`, name.slice(0, 1).toUpperCase()); }
function toast(message) { $('#toast').textContent = message; $('#toast').hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => { $('#toast').hidden = true; }, 5000); }
async function api(url, options = {}) {
  const headers = { 'X-CSRFToken': csrf, ...options.headers };
  if (options.body && !(options.body instanceof FormData)) { headers['Content-Type'] = 'application/json'; options.body = JSON.stringify(options.body); }
  let response;
  try { response = await fetch(url, { ...options, headers }); } catch { throw new Error('ارتباط قطع شد. پیش‌نویس شما ذخیره شده است. دوباره تلاش کنید.'); }
  if (response.redirected && response.url.includes('/accounts/')) { location.href = '/accounts/login/'; throw new Error('لطفاً دوباره وارد حساب شوید.'); }
  let data; try { data = await response.json(); } catch { throw new Error(response.status === 403 ? 'اجازهٔ انجام این کار را ندارید.' : 'انجام درخواست ممکن نشد. دوباره تلاش کنید.'); }
  if (!response.ok) throw new Error(data.error || 'انجام درخواست ممکن نشد.');
  return data;
}
function modal(title, content) { $('#modal-title').textContent = title; $('#modal-body').replaceChildren(content); if (!$('#modal').open) $('#modal').showModal(); }
$('#close-modal').onclick = () => $('#modal').close();
$('#modal').addEventListener('click', (event) => { if (event.target === $('#modal') && (event.clientX < $('#modal').getBoundingClientRect().left || event.clientX > $('#modal').getBoundingClientRect().right)) $('#modal').close(); });
function field(form, label, name, options = {}) {
  const id = `field-${name}`; const labelNode = el('label', '', label); labelNode.htmlFor = id;
  const input = el('input'); Object.assign(input, { name, id, required: true, ...options }); form.append(labelNode, input); return input;
}
function submitButton(form, label) { const button = el('button', 'primary', label); button.type = 'submit'; form.append(button); return button; }
function formAction(form, action) { form.onsubmit = async (event) => { event.preventDefault(); const button = form.querySelector('[type=submit]'); button.disabled = true; try { await action(new FormData(form)); } catch (error) { toast(error.message); } finally { button.disabled = false; } }; }
async function refresh() {
  const data = await api(`/api/workspaces/${workspace}/`); Object.assign(state, data);
  $('#profile').textContent = state.me.name.slice(0, 1).toUpperCase();
  $('#invite-button').hidden = state.me.role !== 'admin';
  $('#member-count').textContent = number.format(state.members.length);
  renderNav();
  if (state.socket?.readyState === WebSocket.OPEN) state.socket.send(JSON.stringify({ event: 'ping' }));
}
function scheduleRefresh() { clearTimeout(refreshTimer); refreshTimer = setTimeout(() => refresh().catch((error) => toast(error.message)), 200); }
function renderNav() {
  $('#channels').replaceChildren(); $('#directs').replaceChildren();
  let unread = 0;
  for (const channel of state.channels) {
    unread += channel.unread;
    const button = el('button', `channel-row${state.current?.id === channel.id ? ' active' : ''}`);
    button.dataset.channel = channel.id;
    if (channel.kind === 'dm') {
      button.append(avatar(channel.name, channel.id, true));
      const person = state.members.find((member) => member.name === channel.name);
      button.append(el('i', `dm-dot${person?.online ? ' online' : ''}`));
    } else button.append(el('span', 'symbol', channel.kind === 'private' ? '⌑' : '#'));
    button.append(el('span', '', channel.name));
    if (channel.unread) button.append(el('span', 'count', number.format(channel.unread)));
    button.setAttribute('aria-current', state.current?.id === channel.id ? 'page' : 'false');
    button.onclick = () => openChannel(channel.id).catch((error) => toast(error.message));
    $(channel.kind === 'dm' ? '#directs' : '#channels').append(button);
  }
  $('#unread-count').textContent = number.format(unread);
  $('#activity-count').hidden = unread === 0;
}
const draftKey = (id) => `teamflow:${state.me?.id}:${workspace}:${id}`;
function saveDraft() {
  if (!state.current) return;
  try { const key = draftKey(state.current.id); const old = JSON.parse(sessionStorage.getItem(key) || '{}'); sessionStorage.setItem(key, JSON.stringify({ body: $('#message-input').value, clientId: old.clientId || crypto.randomUUID() })); } catch { /* Storage can be disabled by the browser. */ }
}
function draft() { try { return JSON.parse(sessionStorage.getItem(draftKey(state.current.id)) || '{}'); } catch { return {}; } }
function clearReply() { state.reply = null; $('#reply-banner').hidden = true; }
async function openChannel(id) {
  if ($('#send-button').disabled) { toast('منتظر بمانید تا ارسال پیام تمام شود.'); return; }
  saveDraft();
  const channel = state.channels.find((item) => item.id === Number(id)); if (!channel) return;
  state.current = channel; state.messages.clear(); state.activeRequest += 1; const requestId = state.activeRequest;
  $('#sidebar').classList.remove('open'); $('#search-results').hidden = true; $('#channel-name').textContent = channel.name;
  $('#channel-symbol').textContent = channel.kind === 'private' ? '⌑' : channel.kind === 'dm' ? '◌' : '#';
  $('#channel-description').textContent = channel.description || (channel.kind === 'dm' ? 'گفتگویی دونفره؛ فضایی برای صحبت و هماهنگی.' : 'فضایی مشترک برای تیم شما.');
  $('#welcome-name').textContent = `${channel.kind === 'dm' ? '' : '#'}${channel.name}`;
  $('#welcome-description').textContent = channel.description || 'فضایی مشترک برای ایده‌ها، خبرها و گفتگوهای روزمره.';
  $('#channel-welcome').hidden = false;
  $('#message-input').placeholder = `پیام به ${channel.kind === 'dm' ? '' : '#'}${channel.name}…`;
  $('#message-input').value = draft().body || ''; $('#attachment').value = ''; $('#file-preview').hidden = true; clearReply();
  $('#message-list').replaceChildren(el('p', 'muted', 'در حال بارگذاری گفتگو…')); $('#load-older').hidden = true;
  localStorage.setItem(`teamflow-channel:${workspace}`, channel.id); renderNav();
  try {
    const data = await api(`/api/channels/${id}/messages/`); if (requestId !== state.activeRequest) return;
    for (const message of data.messages) state.messages.set(message.id, message);
    state.hasMore = data.has_more; renderMessages(); scrollBottom(); markRead();
  } catch (error) { if (requestId === state.activeRequest) { state.messages.clear(); $('#message-list').replaceChildren(el('p', 'muted', error.message)); } throw error; }
}
function scrollBottom() { const node = $('#message-scroll'); node.scrollTop = node.scrollHeight; }
function messageNode(message) {
  const row = el('article', 'message'); row.id = `message-${message.id}`;
  row.append(avatar(message.sender, message.sender_id));
  const content = el('div', 'message-content'); const meta = el('div', 'message-meta');
  meta.append(el('b', '', message.sender)); if (message.sender_id === state.me.id) meta.append(el('span', 'you', 'شما'));
  const time = el('time', '', new Date(message.created_at).toLocaleTimeString('fa-IR', { hour: '2-digit', minute: '2-digit' })); time.dateTime = message.created_at; meta.append(time);
  if (message.edited_at) meta.append(el('small', 'you', 'ویرایش‌شده')); content.append(meta);
  if (message.reply_to && !message.deleted) { const original = state.messages.get(message.reply_to); content.append(el('div', 'reply-ref', original ? `↳ ${original.sender}: ${original.deleted ? 'پیام حذف شده' : original.body.slice(0, 120)}` : `↳ پاسخ به یک پیام قدیمی‌تر`)); }
  content.append(el('p', `message-body${message.deleted ? ' deleted' : ''}`, message.deleted ? 'این پیام حذف شده است.' : message.body));
  if (message.attachment && !message.deleted) { const link = el('a', 'attachment-link'); link.href = message.attachment.url; link.append(el('span', '', `↧ ${message.attachment.name}`), el('small', '', `${number.format(Math.ceil(message.attachment.size / 1024))} کیلوبایت`)); content.append(link); }
  if (!message.deleted) {
    const actions = el('div', 'message-actions');
    const reply = el('button', '', 'پاسخ'); reply.onclick = () => { state.reply = message.id; $('#reply-banner').replaceChildren(document.createTextNode(`پاسخ به ${message.sender}: ${message.body.slice(0, 90)}`)); const cancel = el('button', '', '×'); cancel.type = 'button'; cancel.setAttribute('aria-label', 'لغو پاسخ'); cancel.onclick = clearReply; $('#reply-banner').append(cancel); $('#reply-banner').hidden = false; $('#message-input').focus(); }; actions.append(reply);
    if (message.sender_id === state.me.id) { const edit = el('button', '', 'ویرایش'); edit.onclick = () => editMessage(message); actions.append(edit); }
    if (message.sender_id === state.me.id || state.me.role === 'admin') { const remove = el('button', '', 'حذف'); remove.onclick = () => deleteMessage(message); actions.append(remove); }
    content.append(actions);
  }
  row.append(content); return row;
}
function renderMessages() {
  const list = $('#message-list'); list.replaceChildren(); let date = '';
  for (const message of [...state.messages.values()].sort((a, b) => a.id - b.id)) {
    const label = new Date(message.created_at).toLocaleDateString('fa-IR', { weekday: 'long', month: 'long', day: 'numeric' });
    if (label !== date) { list.append(el('div', 'date-divider', label)); date = label; }
    list.append(messageNode(message));
  }
  $('#empty-state').hidden = state.messages.size > 0; $('#load-older').hidden = !state.hasMore;
}
async function markRead() {
  if (document.hidden || !state.current || !state.messages.size) return;
  const latest = Math.max(...state.messages.keys());
  try { await api(`/api/channels/${state.current.id}/read/`, { method: 'POST', body: { message_id: latest } }); state.current.unread = 0; const channel = state.channels.find((item) => item.id === state.current.id); if (channel) channel.unread = 0; renderNav(); } catch (error) { toast(error.message); }
}
$('#load-older').onclick = async () => {
  if (state.loading) return; state.loading = true;
  const id = state.current.id; const before = Math.min(...state.messages.keys()); const scroll = $('#message-scroll'); const height = scroll.scrollHeight;
  try { const data = await api(`/api/channels/${id}/messages/?before=${before}`); if (state.current.id !== id) return; for (const message of data.messages) state.messages.set(message.id, message); state.hasMore = data.has_more; renderMessages(); scroll.scrollTop += scroll.scrollHeight - height; } catch (error) { toast(error.message); } finally { state.loading = false; }
};
function editMessage(message) {
  const form = el('form'); const area = el('textarea'); area.required = true; area.maxLength = 4000; area.rows = 5; area.value = message.body; area.setAttribute('aria-label', 'ویرایش پیام'); form.append(area); submitButton(form, 'ذخیرهٔ تغییرات');
  formAction(form, async () => { const data = await api(`/api/messages/${message.id}/`, { method: 'PATCH', body: { body: area.value } }); state.messages.set(message.id, data.message); renderMessages(); $('#modal').close(); }); modal('ویرایش پیام', form);
}
function deleteMessage(message) {
  const form = el('form'); form.append(el('p', '', 'این پیام حذف شود؟ متن و پیوست آن دیگر در گفتگو نمایش داده نمی‌شوند.')); submitButton(form, 'حذف پیام');
  formAction(form, async () => { const data = await api(`/api/messages/${message.id}/`, { method: 'DELETE' }); state.messages.set(message.id, data.message); renderMessages(); $('#modal').close(); }); modal('حذف پیام', form);
}
function connect() {
  const socket = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/workspaces/${workspace}/`); state.socket = socket;
  socket.onopen = () => { $('#connection').textContent = 'متصل'; $('#connection').classList.add('online'); state.reconnect = 1000; };
  socket.onmessage = async ({ data }) => {
    const event = JSON.parse(data);
    if (event.event === 'ready') { await recover().catch((error) => toast(error.message)); return; }
    if (event.event === 'error') { toast(event.error); return; }
    if (event.event === 'update:presence') scheduleRefresh();
    if (event.event === 'start:typing' && event.channel_id === state.current?.id && event.user_id !== state.me.id) { $('#typing').textContent = `${event.name} در حال نوشتن است…`; clearTimeout(typingTimer); typingTimer = setTimeout(() => { $('#typing').textContent = ''; }, 3500); }
    if (event.event === 'stop:typing' && event.channel_id === state.current?.id) $('#typing').textContent = '';
    if (event.message) {
      const message = event.message;
      if (message.channel_id === state.current?.id) {
        const scroll = $('#message-scroll'); const nearBottom = scroll.scrollHeight - scroll.scrollTop - scroll.clientHeight < 140;
        state.messages.set(message.id, message); renderMessages(); if (nearBottom || message.sender_id === state.me.id) { scrollBottom(); markRead(); }
      }
      if (event.event === 'new:message') scheduleRefresh();
    }
  };
  socket.onclose = ({ code }) => {
    $('#connection').textContent = 'اتصال مجدد'; $('#connection').classList.remove('online');
    if (code === 4401) { location.href = '/accounts/login/'; return; }
    if (code === 4403) { toast('دیگر به این فضای کاری دسترسی ندارید.'); return; }
    setTimeout(connect, state.reconnect); state.reconnect = Math.min(state.reconnect * 2, 15000);
  };
  socket.onerror = () => socket.close();
}
async function recover() {
  await refresh();
  if (!state.current) return;
  const channelId = state.current.id;
  if (!state.channels.some((channel) => channel.id === channelId)) { state.current = null; state.messages.clear(); renderMessages(); toast('این گفتگو دیگر در دسترس نیست.'); return; }
  // Reload the latest page as well as missed sends, so edits and deletions recover too.
  let after = state.messages.size ? Math.max(...state.messages.keys()) : 0;
  if (after) {
    let more = true;
    while (more && state.current?.id === channelId) { const page = await api(`/api/channels/${channelId}/messages/?after=${after}`); if (state.current?.id !== channelId) return; for (const message of page.messages) { state.messages.set(message.id, message); after = message.id; } more = page.has_more; }
  }
  const page = await api(`/api/channels/${channelId}/messages/`); if (state.current?.id !== channelId) return;
  for (const message of page.messages) state.messages.set(message.id, message);
  state.hasMore = page.has_more && state.messages.size <= 50; renderMessages(); scrollBottom(); markRead();
}
$('#compose').onsubmit = async (event) => {
  event.preventDefault(); if (!state.current) return;
  const input = $('#message-input'); const upload = $('#attachment').files[0]; const body = input.value;
  if (!body.trim() && !upload) return;
  saveDraft(); const channelId = state.current.id; const clientId = draft().clientId || crypto.randomUUID();
  const data = new FormData(); data.append('body', body); data.append('client_message_id', clientId); if (state.reply) data.append('reply_to', state.reply); if (upload) data.append('file', upload);
  $('#send-button').disabled = true;
  try {
    const result = await api(`/api/channels/${channelId}/messages/`, { method: 'POST', body: data });
    sessionStorage.removeItem(draftKey(channelId));
    if (state.current?.id === channelId) { input.value = ''; $('#attachment').value = ''; $('#file-preview').hidden = true; input.required = true; clearReply(); state.messages.set(result.message.id, result.message); renderMessages(); scrollBottom(); markRead(); }
    socketSend({ event: 'stop:typing', channel_id: channelId });
  } catch (error) { toast(error.message); } finally { $('#send-button').disabled = false; }
};
function socketSend(data) { if (state.socket?.readyState === WebSocket.OPEN) state.socket.send(JSON.stringify(data)); }
$('#message-input').addEventListener('keydown', (event) => { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); if (!$('#send-button').disabled) $('#compose').requestSubmit(); } });
$('#message-input').addEventListener('input', () => { saveDraft(); if (Date.now() - lastTyping > 2000 && state.current) { lastTyping = Date.now(); socketSend({ event: 'start:typing', channel_id: state.current.id }); } });
$('#attach-button').onclick = () => $('#attachment').click();
$('#attachment').onchange = () => {
  const file = $('#attachment').files[0]; if (!file) { $('#file-preview').hidden = true; $('#message-input').required = true; return; }
  if (file.size > 10 * 1024 * 1024) { toast('حجم فایل باید حداکثر ۱۰ مگابایت باشد.'); $('#attachment').value = ''; return; }
  $('#file-preview').replaceChildren(document.createTextNode(`↧ ${file.name}`)); const clear = el('button', '', '×'); clear.type = 'button'; clear.setAttribute('aria-label', 'حذف فایل'); clear.onclick = () => { $('#attachment').value = ''; $('#file-preview').hidden = true; $('#message-input').required = true; }; $('#file-preview').append(clear); $('#file-preview').hidden = false; $('#message-input').required = false;
};
$('#emoji-button').onclick = () => { const picker = el('div', 'emoji-picker'); for (const emoji of ['👋', '🎉', '👍', '💜', '🙌', '🚀', '✅', '😊']) { const button = el('button', 'icon-button', emoji); button.onclick = () => { $('#message-input').value += emoji; saveDraft(); $('#modal').close(); $('#message-input').focus(); }; picker.append(button); } modal('یک شکلک انتخاب کنید', picker); };
for (const button of document.querySelectorAll('[data-format]')) button.onclick = () => { const input = $('#message-input'); const mark = button.dataset.format; const start = input.selectionStart; const end = input.selectionEnd; input.setRangeText(mark + input.value.slice(start, end) + mark, start, end, 'select'); input.focus(); saveDraft(); };
$('#add-channel').onclick = () => {
  const form = el('form'); field(form, 'نام کانال', 'name', { placeholder: 'مثلاً طراحی', maxLength: 80 }); field(form, 'موضوع این کانال چیست؟', 'description', { placeholder: 'توضیح کوتاهی برای هم‌تیمی‌ها بنویسید', maxLength: 240, required: false });
  const label = el('label', '', 'دسترسی'); label.htmlFor = 'channel-kind'; const kind = el('select'); kind.id = 'channel-kind'; kind.name = 'kind'; for (const [value, text] of [['public', 'عمومی · همهٔ اعضای فضای کاری'], ['private', 'خصوصی · فقط اعضای انتخاب‌شده']]) { const option = el('option', '', text); option.value = value; kind.append(option); } form.append(label, kind);
  const selection = el('div'); selection.hidden = true; selection.append(el('p', '', 'اعضای این کانال را انتخاب کنید. خودتان به‌صورت خودکار عضو هستید.'));
  for (const member of state.members.filter((member) => member.id !== state.me.id)) { const row = el('label', 'check-label'); const checkbox = el('input'); checkbox.type = 'checkbox'; checkbox.name = 'members'; checkbox.value = member.id; row.append(checkbox, document.createTextNode(member.name)); selection.append(row); } form.append(selection); kind.onchange = () => { selection.hidden = kind.value !== 'private'; }; submitButton(form, 'ساخت کانال');
  formAction(form, async (data) => { const result = await api(`/api/workspaces/${workspace}/channels/`, { method: 'POST', body: { name: data.get('name'), description: data.get('description'), kind: data.get('kind'), members: data.getAll('members').map(Number) } }); await refresh(); $('#modal').close(); await openChannel(result.id); }); modal('یک کانال تازه برای همکاری', form);
};
$('#add-dm').onclick = () => showMembers(true);
function showMembers(direct = false) {
  const list = el('div', 'member-list');
  for (const member of state.members) {
    if (direct && member.id === state.me.id) continue;
    const row = el(direct ? 'button' : 'div', 'person'); row.append(avatar(member.name, member.id, true)); const info = el('div', 'person-info'); info.append(el('b', '', `${member.name}${member.id === state.me.id ? ' (شما)' : ''}`), el('small', '', `${member.email} · ${member.online ? 'آنلاین' : 'آفلاین'}`)); row.append(info);
    if (direct) row.onclick = async () => { try { const result = await api(`/api/workspaces/${workspace}/direct/`, { method: 'POST', body: { user_id: member.id } }); await refresh(); $('#modal').close(); await openChannel(result.id); } catch (error) { toast(error.message); } };
    else if (state.me.role === 'admin') {
      const select = el('select'); select.setAttribute('aria-label', `نقش ${member.name}`); for (const role of ['member', 'admin']) { const option = el('option', '', roleLabels[role]); option.value = role; select.append(option); } select.value = member.role; select.onchange = async () => { try { await api(`/api/workspaces/${workspace}/members/${member.id}/`, { method: 'POST', body: { role: select.value } }); await refresh(); showMembers(); } catch (error) { select.value = member.role; toast(error.message); } }; row.append(select);
      const remove = el('button', 'remove', 'حذف'); remove.onclick = () => { const form = el('form'); form.append(el('p', '', `${member.name} از این فضای کاری حذف شود؟ دسترسی او به گفتگوها و فایل‌ها قطع می‌شود.`)); submitButton(form, 'حذف عضو'); formAction(form, async () => { await api(`/api/workspaces/${workspace}/members/${member.id}/`, { method: 'POST', body: { role: 'remove' } }); if (member.id === state.me.id) location.href = '/'; else { await refresh(); showMembers(); } }); modal('حذف عضو', form); }; row.append(remove);
    } else row.append(el('small', 'muted', roleLabels[member.role])); list.append(row);
  }
  if (!list.children.length) list.append(el('p', '', 'برای شروع گفتگوی مستقیم، یک هم‌تیمی دعوت کنید.'));
  modal(direct ? 'شروع گفتگو' : 'هم‌تیمی‌های شما', list);
}
$('#members-button').onclick = () => showMembers(); $('#channel-members').onclick = () => showMembers();
$('#invite-button').onclick = () => {
  const form = el('form'); form.append(el('p', '', 'هم‌تیمی خود را به این فضای کاری دعوت کنید. پیوند تا هفت روز معتبر است و فقط با ایمیل او کار می‌کند.')); field(form, 'نشانی ایمیل', 'email', { type: 'email', dir: 'ltr', placeholder: 'teammate@company.com' }); submitButton(form, 'ارسال دعوت‌نامه');
  formAction(form, async (data) => { const result = await api(`/api/workspaces/${workspace}/invites/`, { method: 'POST', body: { email: data.get('email') } }); const content = el('div'); content.append(el('p', '', `دعوت‌نامه برای ${result.email} ساخته شد. می‌توانید این پیوند را هم مستقیماً به اشتراک بگذارید:`)); const link = el('a', 'invite-result', result.url); link.href = result.url; link.dir = 'ltr'; content.append(link); const copy = el('button', 'primary full', 'کپی پیوند دعوت‌نامه'); copy.style.marginTop = '20px'; copy.onclick = async () => { try { await navigator.clipboard.writeText(result.url); toast('پیوند دعوت‌نامه کپی شد.'); } catch { toast('پیوند دعوت‌نامه را انتخاب و کپی کنید.'); } }; content.append(copy); modal('دعوت‌نامه آماده است', content); }); modal('دعوت هم‌تیمی‌ها', form);
};
$('#workspace-button').onclick = () => { const form = el('form'); form.method = 'post'; form.action = '/workspaces/create/'; const token = el('input'); token.type = 'hidden'; token.name = 'csrfmiddlewaretoken'; token.value = csrf; form.append(token); field(form, 'نام فضای کاری', 'name', { maxLength: 80, placeholder: 'مثلاً استودیوی آفرین' }); submitButton(form, 'ساخت فضای کاری'); modal('یک فضای کاری تازه برای تیم شما', form); };
$('#workspace-select').onchange = (event) => { location.href = `/?workspace=${event.target.value}`; };
$('#search-form').onsubmit = async (event) => {
  event.preventDefault(); const query = $('#search').value.trim(); if (query.length < 2) return;
  $('#search-results').hidden = false; $('#results-list').replaceChildren(el('p', 'muted', 'در حال جستجو…'));
  try { const data = await api(`/api/workspaces/${workspace}/search/?q=${encodeURIComponent(query)}`); const list = $('#results-list'); list.replaceChildren();
    for (const message of data.messages) { const result = el('button', 'result'); result.append(el('small', '', `#${message.channel_name} · ${message.sender} · ${new Date(message.created_at).toLocaleDateString('fa-IR')}`), document.createTextNode(message.body)); result.onclick = async () => { try { await openChannel(message.channel_id); if (!state.messages.has(message.id)) { state.messages.set(message.id, message); renderMessages(); } $(`#message-${message.id}`)?.scrollIntoView({ block: 'center' }); } catch (error) { toast(error.message); } }; list.append(result); }
    if (!data.messages.length) list.append(el('p', 'no-results', 'پیامی پیدا نشد. عبارت دیگری را امتحان کنید.'));
  } catch (error) { $('#results-list').replaceChildren(el('p', 'muted', error.message)); }
};
$('#close-search').onclick = () => { $('#search-results').hidden = true; };
function showActivity() {
  const list = el('div'); const unread = state.channels.filter((channel) => channel.unread > 0);
  for (const channel of unread) { const button = el('button', 'activity-card'); button.append(el('b', '', `${channel.kind === 'dm' ? '' : '#'}${channel.name}`), el('span', 'count', `${number.format(channel.unread)} خوانده‌نشده`)); button.onclick = () => { $('#modal').close(); openChannel(channel.id).catch((error) => toast(error.message)); }; list.append(button); }
  if (!unread.length) list.append(el('p', '', 'همهٔ پیام‌ها را خوانده‌اید. حالا وقت تمرکز است.')); modal('گفتگوهای خوانده‌نشدهٔ شما', list);
}
$('#activity-button').onclick = showActivity; $('#unread-button').onclick = showActivity;
$('#all-button').onclick = () => { const list = el('div'); for (const channel of state.channels) { const button = el('button', 'activity-card', `${channel.kind === 'dm' ? '' : '#'}${channel.name}`); button.onclick = () => { $('#modal').close(); openChannel(channel.id).catch((error) => toast(error.message)); }; list.append(button); } modal('همهٔ گفتگوها', list); };
$('#home-button').onclick = () => { $('#search-results').hidden = true; if (state.channels.length) openChannel(state.channels[0].id).catch((error) => toast(error.message)); };
$('#messages-tab').onclick = () => { $('#search-results').hidden = true; };
$('#mobile-menu').onclick = () => $('#sidebar').classList.toggle('open');
document.addEventListener('visibilitychange', () => { if (!document.hidden) { recover().catch((error) => toast(error.message)); } });
window.addEventListener('online', () => { if (state.socket?.readyState === WebSocket.CLOSED) connect(); });
setInterval(() => { socketSend({ event: 'ping' }); refresh().catch(() => {}); }, 20000);
(async () => { try { await refresh(); const stored = Number(localStorage.getItem(`teamflow-channel:${workspace}`)); const channel = state.channels.find((item) => item.id === stored) || state.channels.find((item) => item.name === 'general') || state.channels[0]; if (channel) await openChannel(channel.id); connect(); } catch (error) { toast(error.message); } })();
