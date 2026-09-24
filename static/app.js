const categorySelect = document.querySelector('#category');
const submitCategory = document.querySelector('[name="category"]');
const noticeList = document.querySelector('#notice-list');
const emptyState = document.querySelector('#empty-state');
const count = document.querySelector('#notice-count');
const search = document.querySelector('#search');
const dialog = document.querySelector('#submit-dialog');
const form = document.querySelector('#submit-form');
const formMessage = document.querySelector('#form-message');
const reviewQueue = document.querySelector('#review-queue');
const queueCount = document.querySelector('#queue-count');
const moderatorLogin = document.querySelector('#moderator-login');
const loginForm = document.querySelector('#login-form');
const loginMessage = document.querySelector('#login-message');
const signOut = document.querySelector('#sign-out');
const publicArchive = document.querySelector('#public-archive');
const publicArchiveEmpty = document.querySelector('#public-archive-empty');
const archiveCount = document.querySelector('#archive-count');
const moderatorArchive = document.querySelector('#moderator-archive');
const moderatorArchiveList = document.querySelector('#moderator-archive-list');
const moderatorArchiveCount = document.querySelector('#moderator-archive-count');
let authenticated = false;

function optionMarkup(categories) {
  return categories.map(category => `<option value="${category}">${category}</option>`).join('');
}

async function loadCategories() {
  const response = await fetch('/api/categories');
  const { categories } = await response.json();
  categorySelect.insertAdjacentHTML('beforeend', optionMarkup(categories));
  submitCategory.insertAdjacentHTML('beforeend', optionMarkup(categories));
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character]));
}

function noticeMarkup(notice) {
  const deleteAction = authenticated ? `<button class="delete-button" type="button" data-delete-id="${notice.id}">Delete notice</button>` : '';
  return `<article class="notice"><div class="notice-meta"><span>${escapeHtml(notice.category)}</span><span>Until ${escapeHtml(notice.expires_on)}</span></div><h3>${escapeHtml(notice.title)}</h3><p>${escapeHtml(notice.description)}</p><div class="notice-footer"><span>${escapeHtml(notice.location)}</span><span>${escapeHtml(notice.contact)}</span></div>${deleteAction}</article>`;
}

async function loadNotices() {
  const params = new URLSearchParams({ search: search.value, category: categorySelect.value });
  const response = await fetch(`/api/notices?${params}`);
  const { notices } = await response.json();
  noticeList.innerHTML = notices.map(noticeMarkup).join('');
  emptyState.hidden = notices.length !== 0;
  count.textContent = `${notices.length} ${notices.length === 1 ? 'notice' : 'notices'}`;
  noticeList.querySelectorAll('[data-delete-id]').forEach(button => button.addEventListener('click', () => deleteNotice(button.dataset.deleteId)));
}

async function loadPublicArchive() {
  const response = await fetch('/api/archive');
  if (!response.ok) {
    publicArchive.innerHTML = '';
    publicArchiveEmpty.hidden = false;
    archiveCount.textContent = '';
    return;
  }
  const { notices } = await response.json();
  publicArchive.innerHTML = notices.map(notice => archiveNoticeMarkup(notice)).join('');
  publicArchiveEmpty.hidden = notices.length !== 0;
  archiveCount.textContent = `${notices.length} archived`;
  publicArchive.querySelectorAll('[data-restore-id]').forEach(button => button.addEventListener('click', () => restoreNotice(button.dataset.restoreId)));
  publicArchive.querySelectorAll('[data-final-delete-id]').forEach(button => button.addEventListener('click', () => finalDeleteNotice(button.dataset.finalDeleteId)));
}

function archiveNoticeMarkup(notice) {
  const actions = authenticated ? `<div class="archive-actions"><button type="button" data-restore-id="${notice.id}">Undo</button><button type="button" data-final-delete-id="${notice.id}">Delete permanently</button></div>` : '';
  return `<article class="notice archive-notice"><div class="notice-meta"><span>${escapeHtml(notice.category)}</span><span>Expired ${escapeHtml(notice.expires_on)}</span></div><h3>${escapeHtml(notice.title)}</h3><p>${escapeHtml(notice.description)}</p><div class="notice-footer"><span>${escapeHtml(notice.location)}</span><span>${escapeHtml(notice.contact)}</span></div>${actions}</article>`;
}

async function submitNotice(event) {
  event.preventDefault();
  formMessage.textContent = '';
  const data = Object.fromEntries(new FormData(form));
  const response = await fetch('/api/notices', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
  const result = await response.json();
  if (!response.ok) {
    formMessage.textContent = result.error || 'Please check the form.';
    return;
  }
  form.reset();
  dialog.close();
  window.alert('Thanks. Your notice has been sent for review.');
  loadQueue();
}

async function moderate(id, status) {
  await fetch(`/api/notices/${status}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id }) });
  loadQueue();
  loadNotices();
}

async function deleteNotice(id) {
  if (!window.confirm('Delete this notice permanently?')) return;
  const response = await fetch('/api/notices/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id }) });
  if (response.ok) {
    loadQueue();
    loadNotices();
  }
}

async function finalDeleteNotice(id) {
  if (!window.confirm('Permanently delete this notice and its record? This cannot be undone.')) return;
  const response = await fetch('/api/notices/final-delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id }) });
  if (response.ok) refreshNoticeViews();
}

async function restoreNotice(id) {
  if (!window.confirm('Restore this notice? Rejected notices return to the review queue.')) return;
  const response = await fetch('/api/notices/restore', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id }) });
  if (response.ok) refreshNoticeViews();
}

function refreshNoticeViews() {
  loadNotices();
  loadPublicArchive();
  loadQueue();
}

async function loadQueue() {
  const response = await fetch('/api/moderation');
  if (!response.ok) {
    moderatorLogin.hidden = false;
    reviewQueue.hidden = true;
    queueCount.textContent = '';
    return;
  }
  const { notices } = await response.json();
  moderatorLogin.hidden = true;
  reviewQueue.hidden = false;
  moderatorArchive.hidden = false;
  queueCount.textContent = `${notices.length} awaiting review`;
  reviewQueue.innerHTML = notices.length ? notices.map(notice => `<div class="review-item"><div><h3>${escapeHtml(notice.title)}</h3><p>${escapeHtml(notice.category)} · ${escapeHtml(notice.location)} · ${escapeHtml(notice.contact)}</p></div><div class="review-actions"><button type="button" data-id="${notice.id}" data-status="approve">Approve</button><button type="button" data-id="${notice.id}" data-status="reject">Reject</button><button type="button" data-delete-id="${notice.id}">Delete</button></div></div>`).join('') : '<p class="empty-state">No notices are waiting for review.</p>';
  reviewQueue.querySelectorAll('[data-status]').forEach(button => button.addEventListener('click', () => moderate(button.dataset.id, button.dataset.status)));
  reviewQueue.querySelectorAll('[data-delete-id]').forEach(button => button.addEventListener('click', () => deleteNotice(button.dataset.deleteId)));
  loadModeratorArchive();
}

async function loadModeratorArchive() {
  const response = await fetch('/api/moderation/archive');
  if (!response.ok) return;
  const { notices } = await response.json();
  moderatorArchiveCount.textContent = `${notices.length} archived`;
  moderatorArchiveList.innerHTML = notices.length ? notices.map(notice => `<div class="review-item archive-item"><div><h3>${escapeHtml(notice.title)}</h3><p>${escapeHtml(notice.category)} · ${notice.deleted_at ? 'Withdrawn by moderator' : 'Rejected'}</p></div><div class="archive-actions"><button type="button" data-restore-id="${notice.id}">Undo</button><button type="button" data-final-delete-id="${notice.id}">Delete permanently</button></div></div>`).join('') : '<p class="empty-state">No rejected or withdrawn notices.</p>';
  moderatorArchiveList.querySelectorAll('[data-restore-id]').forEach(button => button.addEventListener('click', () => restoreNotice(button.dataset.restoreId)));
  moderatorArchiveList.querySelectorAll('[data-final-delete-id]').forEach(button => button.addEventListener('click', () => finalDeleteNotice(button.dataset.finalDeleteId)));
}

async function loadSession() {
  const response = await fetch('/api/session');
  const { authenticated: sessionAuthenticated } = await response.json();
  authenticated = sessionAuthenticated;
  signOut.hidden = !sessionAuthenticated;
  if (sessionAuthenticated) {
    loadPublicArchive();
    loadQueue();
  }
}

async function login(event) {
  event.preventDefault();
  loginMessage.textContent = '';
  const response = await fetch('/api/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password: document.querySelector('#password').value }) });
  const result = await response.json();
  if (!response.ok) {
    loginMessage.textContent = result.error;
    return;
  }
  loginForm.reset();
  authenticated = true;
  signOut.hidden = false;
  loadNotices();
  loadPublicArchive();
  loadQueue();
}

async function logout() {
  await fetch('/api/logout', { method: 'POST' });
  authenticated = false;
  signOut.hidden = true;
  reviewQueue.hidden = true;
  moderatorArchive.hidden = true;
  reviewQueue.innerHTML = '';
  moderatorArchiveList.innerHTML = '';
  queueCount.textContent = '';
  moderatorLogin.hidden = false;
  loadNotices();
}

document.querySelector('#open-submit').addEventListener('click', () => dialog.showModal());
document.querySelector('#close-submit').addEventListener('click', () => dialog.close());
form.addEventListener('submit', submitNotice);
loginForm.addEventListener('submit', login);
signOut.addEventListener('click', logout);
search.addEventListener('input', loadNotices);
categorySelect.addEventListener('change', loadNotices);

loadCategories().then(loadNotices).then(loadPublicArchive).then(loadSession).catch(() => {
  noticeList.innerHTML = '<p class="empty-state">The noticeboard is temporarily unavailable.</p>';
});
