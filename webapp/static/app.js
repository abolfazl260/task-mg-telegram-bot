(() => {
  const tg = window.Telegram?.WebApp;
  if (tg) { tg.ready(); tg.expand(); }
  const state = document.getElementById('state');
  const tasksEl = document.getElementById('tasks');
  const searchEl = document.getElementById('search');
  const statusEl = document.getElementById('status-filter');
  const refreshEl = document.getElementById('refresh');
  const reportEl = document.getElementById('status-report');
  let tasks = [];
  const pageParams = new URLSearchParams(window.location.search);
  const botKey = pageParams.get('bot_key') || '';
  const initData = tg?.initData || '';
  const headers = initData ? { 'X-Telegram-Init-Data': initData } : {};
  const apiUrl = (path) => `${path}?bot_key=${encodeURIComponent(botKey)}`;
  function text(value) { return String(value ?? '').replace(/[&<>\"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#039;'}[ch])); }
  const statusLabels = { pending: 'در انتظار', in_progress: 'در حال انجام', done: 'انجام‌شده', cancelled: 'لغوشده' };
  const statusColors = { pending: '#f79009', in_progress: '#4f6bed', done: '#12b76a', cancelled: '#f04438' };
  function renderReport() {
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
      return `<div class="report-item" title="${text(statusLabels[item.status])}: ${item.count} وظیفه (${percentage.toFixed(1)}%)"><span class="report-swatch" style="background:${statusColors[item.status]}"></span><span>${text(statusLabels[item.status])}</span><strong>${item.count}</strong><small>${percentage.toFixed(1)}%</small></div>`;
    }).join('');
    reportEl.innerHTML = `<div class="report-content"><div class="report-pie-wrap"><div class="report-pie" style="background:conic-gradient(${segments})" aria-label="گزارش وضعیت وظایف"><div class="report-pie-center"><strong>${total}</strong><span>کل وظایف</span></div></div></div><div class="report-legend">${legend}</div></div>`;
  }
  function render() {
    const query = searchEl.value.trim().toLowerCase();
    const status = statusEl.value;
    const filtered = tasks.filter(task => {
      const haystack = `${task.title || ''} ${task.description || ''} ${task.category || ''} ${task.tags || ''}`.toLowerCase();
      return (!query || haystack.includes(query)) && (!status || task.status === status);
    });
    if (!filtered.length) { tasksEl.innerHTML = ''; state.hidden = false; state.textContent = tasks.length ? 'وظیفه‌ای با این فیلتر پیدا نشد.' : 'وظیفه‌ای برای نمایش وجود ندارد.'; return; }
    state.hidden = true;
    tasksEl.innerHTML = filtered.map(task => `<article class="task" data-task-id="${text(task.id)}"><h2 class="task-title">${text(task.title || 'بدون عنوان')}</h2><div class="task-meta">${task.status ? `<span class="badge">${text(statusLabels[task.status] || task.status)}</span>` : ''}${task.priority ? `<span class="badge">اولویت: ${text(task.priority)}</span>` : ''}${task.deadline ? `<span>مهلت: ${text(task.deadline)}</span>` : ''}${task.category ? `<span>دسته: ${text(task.category)}</span>` : ''}</div></article>`).join('');
    tasksEl.querySelectorAll('[data-task-id]').forEach(card => card.addEventListener('click', () => { window.location.href = `/static/task.html?id=${encodeURIComponent(card.dataset.taskId)}&bot_key=${encodeURIComponent(botKey)}`; }));
  }
  async function load() {
    state.hidden = false; state.textContent = 'در حال دریافت وظایف...';
    try { const response = await fetch(apiUrl('/api/tasks'), { headers }); if (!response.ok) throw new Error(`HTTP ${response.status}`); const data = await response.json(); tasks = Array.isArray(data.tasks) ? data.tasks : []; renderReport(); render(); }
    catch (error) { tasksEl.innerHTML = ''; state.hidden = false; state.textContent = 'دریافت وظایف انجام نشد.'; reportEl.innerHTML = '<div class="report-empty">گزارش وضعیت در دسترس نیست.</div>'; console.error(error); }
  }
  searchEl.addEventListener('input', render); statusEl.addEventListener('change', render); refreshEl.addEventListener('click', load); load();
})();
