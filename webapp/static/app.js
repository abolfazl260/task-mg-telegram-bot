(() => {
  const tg = window.Telegram?.WebApp;
  if (tg) { tg.ready(); tg.expand(); }

  const state = document.getElementById('state');
  const tasksEl = document.getElementById('tasks');
  const searchEl = document.getElementById('search');
  const statusEl = document.getElementById('status-filter');
  const refreshEl = document.getElementById('refresh');
  const themeToggleEl = document.getElementById('theme-toggle');
  const reportEl = document.getElementById('status-report');
  const priorityReportEl = document.getElementById('priority-report');
  const userCardEl = document.getElementById('user-card');
  const paginationEl = document.getElementById('pagination');
  const prevPageEl = document.getElementById('prev-page');
  const nextPageEl = document.getElementById('next-page');
  const pageInfoEl = document.getElementById('page-info');
  const pageSizeEl = document.getElementById('page-size');
  const resultCountEl = document.getElementById('result-count');

  let tasks = [];
  let currentPage = 1;
  let pageSize = Number(pageSizeEl.value) || 10;
  const pageParams = new URLSearchParams(window.location.search);
  const botKey = pageParams.get('bot_key') || '';
  const initData = tg?.initData || '';
  const headers = initData ? { 'X-Telegram-Init-Data': initData } : {};
  const apiUrl = (path) => `${path}?bot_key=${encodeURIComponent(botKey)}`;

  function text(value) {
    return String(value ?? '').replace(/[&<>\"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#039;'}[ch]));
  }

  const statusLabels = { pending: 'در انتظار', in_progress: 'در حال انجام', done: 'انجام‌شده', cancelled: 'لغوشده' };
  const statusColors = { pending: '#f79009', in_progress: '#4f6bed', done: '#12b76a', cancelled: '#f04438' };
  const priorityLabels = { low: 'کم', medium: 'متوسط', high: 'زیاد', urgent: 'فوری' };
  const priorityColors = { low: '#98a2b3', medium: '#4f6bed', high: '#f79009', urgent: '#f04438' };

  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('task-dashboard-theme', theme);
    themeToggleEl.textContent = theme === 'dark' ? '☀' : '☾';
    themeToggleEl.setAttribute('aria-label', theme === 'dark' ? 'فعال‌سازی حالت روشن' : 'فعال‌سازی حالت تاریک');
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = theme === 'dark' ? '#101828' : '#ffffff';
  }

  function initTheme() {
    const saved = localStorage.getItem('task-dashboard-theme');
    const telegramTheme = tg?.colorScheme === 'dark' ? 'dark' : 'light';
    applyTheme(saved || telegramTheme);
  }

  function renderTelegramUser(user) {
    if (!user) return;
    const fullName = [user.first_name, user.last_name].filter(Boolean).join(' ').trim() || 'کاربر تلگرام';
    const username = user.username ? `@${text(user.username)}` : '';
    const avatar = user.photo_url
      ? `<img class="user-avatar" src="${text(user.photo_url)}" alt="${text(fullName)}">`
      : `<span class="user-avatar-fallback">${text(fullName.charAt(0))}</span>`;
    userCardEl.innerHTML = `<div class="user-card-content">${avatar}<div class="user-card-copy"><strong>${text(fullName)}</strong><span>${username || 'پروفایل تلگرام'}</span></div><span class="telegram-badge">Telegram</span></div>`;
    userCardEl.hidden = false;
    document.getElementById('greeting').textContent = `سلام ${text(user.first_name || '')}`.trim();
  }

  async function loadTelegramUser() {
    if (!initData) return;
    try {
      const response = await fetch(apiUrl('/api/me'), { headers, cache: 'no-store' });
      if (!response.ok) return;
      const data = await response.json();
      renderTelegramUser(data.user);
    } catch (error) { console.warn('Telegram profile unavailable', error); }
  }

  function renderStatusReport() {
    const statuses = ['pending', 'in_progress', 'done', 'cancelled'].map(status => ({ status, count: tasks.filter(task => task.status === status).length }));
    const total = statuses.reduce((sum, item) => sum + item.count, 0);
    if (!total) { reportEl.innerHTML = '<div class="report-empty">هنوز وظیفه‌ای برای نمایش گزارش وجود ندارد.</div>'; return; }
    let start = 0;
    const segments = statuses.filter(item => item.count).map(item => {
      const percentage = item.count / total * 100;
      const end = start + percentage * 3.6;
      const segment = `${statusColors[item.status]} ${start}deg ${end}deg`;
      start = end;
      return segment;
    }).join(', ');
    const legend = statuses.map(item => {
      const percentage = item.count / total * 100;
      return `<div class="report-item"><span class="report-swatch" style="background:${statusColors[item.status]}"></span><span>${text(statusLabels[item.status])}</span><strong>${item.count}</strong><small>${percentage.toFixed(1)}%</small></div>`;
    }).join('');
    reportEl.innerHTML = `<div class="report-content"><div class="report-pie-wrap"><div class="report-pie" style="background:conic-gradient(${segments})" aria-label="گزارش وضعیت وظایف"><div class="report-pie-center"><strong>${total}</strong><span>کل وظایف</span></div></div></div><div class="report-legend">${legend}</div></div>`;
  }

  function renderPriorityReport() {
    const priorities = ['urgent', 'high', 'medium', 'low'].map(priority => ({ priority, count: tasks.filter(task => String(task.priority || 'medium').toLowerCase() === priority).length }));
    const total = priorities.reduce((sum, item) => sum + item.count, 0);
    if (!total) { priorityReportEl.innerHTML = '<div class="report-empty">هنوز وظیفه‌ای برای نمایش گزارش وجود ندارد.</div>'; return; }
    const max = Math.max(...priorities.map(item => item.count), 1);
    priorityReportEl.innerHTML = `<div class="priority-chart">${priorities.map(item => `<div class="priority-row"><div class="priority-label"><span>${text(priorityLabels[item.priority])}</span><strong>${item.count}</strong></div><div class="priority-track"><span style="width:${item.count / max * 100}%;background:${priorityColors[item.priority]}"></span></div><small>${(item.count / total * 100).toFixed(1)}%</small></div>`).join('')}</div>`;
  }

  function filteredTasks() {
    const query = searchEl.value.trim().toLowerCase();
    const status = statusEl.value;
    return tasks.filter(task => {
      const haystack = `${task.title || ''} ${task.description || ''} ${task.category || ''} ${task.tags || ''}`.toLowerCase();
      return (!query || haystack.includes(query)) && (!status || task.status === status);
    });
  }

  function renderPagination(total) {
    const totalPages = Math.max(1, Math.ceil(total / pageSize));
    currentPage = Math.min(currentPage, totalPages);
    paginationEl.hidden = total <= pageSize;
    prevPageEl.disabled = currentPage <= 1;
    nextPageEl.disabled = currentPage >= totalPages;
    pageInfoEl.textContent = `صفحه ${currentPage} از ${totalPages}`;
    resultCountEl.textContent = `${total} وظیفه`;
  }

  function render() {
    const filtered = filteredTasks();
    const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
    if (currentPage > totalPages) currentPage = totalPages;
    const start = (currentPage - 1) * pageSize;
    const visible = filtered.slice(start, start + pageSize);
    renderPagination(filtered.length);
    if (!visible.length) {
      tasksEl.innerHTML = '';
      state.hidden = false;
      state.textContent = tasks.length ? 'وظیفه‌ای با این فیلتر پیدا نشد.' : 'وظیفه‌ای برای نمایش وجود ندارد.';
      return;
    }
    state.hidden = true;
    tasksEl.innerHTML = visible.map(task => `<article class="task" data-task-id="${text(task.id)}"><h2 class="task-title">${text(task.title || 'بدون عنوان')}</h2><div class="task-meta">${task.status ? `<span class="badge">${text(statusLabels[task.status] || task.status)}</span>` : ''}${task.priority ? `<span class="badge">اولویت: ${text(priorityLabels[task.priority] || task.priority)}</span>` : ''}${task.deadline ? `<span>مهلت: ${text(task.deadline)}</span>` : ''}${task.category ? `<span>دسته: ${text(task.category)}</span>` : ''}</div></article>`).join('');
    tasksEl.querySelectorAll('[data-task-id]').forEach(card => card.addEventListener('click', () => { window.location.href = `/static/task.html?id=${encodeURIComponent(card.dataset.taskId)}&bot_key=${encodeURIComponent(botKey)}`; }));
  }

  async function load() {
    state.hidden = false; state.textContent = 'در حال دریافت وظایف...';
    try {
      const response = await fetch(apiUrl('/api/tasks'), { headers, cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      tasks = Array.isArray(data.tasks) ? data.tasks : [];
      currentPage = 1;
      renderStatusReport();
      renderPriorityReport();
      render();
    } catch (error) {
      tasksEl.innerHTML = ''; state.hidden = false; state.textContent = 'دریافت وظایف انجام نشد.';
      reportEl.innerHTML = '<div class="report-empty">گزارش وضعیت در دسترس نیست.</div>';
      priorityReportEl.innerHTML = '<div class="report-empty">گزارش اولویت در دسترس نیست.</div>';
      console.error(error);
    }
  }

  initTheme();
  loadTelegramUser();
  searchEl.addEventListener('input', () => { currentPage = 1; render(); });
  statusEl.addEventListener('change', () => { currentPage = 1; render(); });
  pageSizeEl.addEventListener('change', () => { pageSize = Number(pageSizeEl.value) || 10; currentPage = 1; render(); });
  prevPageEl.addEventListener('click', () => { if (currentPage > 1) { currentPage -= 1; render(); } });
  nextPageEl.addEventListener('click', () => { const totalPages = Math.max(1, Math.ceil(filteredTasks().length / pageSize)); if (currentPage < totalPages) { currentPage += 1; render(); } });
  refreshEl.addEventListener('click', load);
  themeToggleEl.addEventListener('click', () => applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'));
  if (tg?.onEvent) tg.onEvent('themeChanged', () => { if (!localStorage.getItem('task-dashboard-theme')) applyTheme(tg.colorScheme === 'dark' ? 'dark' : 'light'); });
  load();
})();
