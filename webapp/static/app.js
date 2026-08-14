(() => {
  const tg = window.Telegram?.WebApp;
  if (tg) { tg.ready(); tg.expand(); }
  const state = document.getElementById('state');
  const tasksEl = document.getElementById('tasks');
  const searchEl = document.getElementById('search');
  const statusEl = document.getElementById('status-filter');
  const refreshEl = document.getElementById('refresh');
  let tasks = [];
  const pageParams = new URLSearchParams(window.location.search);
  const botKey = pageParams.get('bot_key') || '';
  const initData = tg?.initData || '';
  const headers = initData ? { 'X-Telegram-Init-Data': initData } : {};
  const apiUrl = (path) => `${path}?bot_key=${encodeURIComponent(botKey)}`;
  function text(value) { return String(value ?? '').replace(/[&<>\"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#039;'}[ch])); }
  function render() {
    const query = searchEl.value.trim().toLowerCase();
    const status = statusEl.value;
    const filtered = tasks.filter(task => {
      const haystack = `${task.title || ''} ${task.description || ''} ${task.category || ''} ${task.tags || ''}`.toLowerCase();
      return (!query || haystack.includes(query)) && (!status || task.status === status);
    });
    if (!filtered.length) { tasksEl.innerHTML = ''; state.hidden = false; state.textContent = tasks.length ? 'وظیفه‌ای با این فیلتر پیدا نشد.' : 'وظیفه‌ای برای نمایش وجود ندارد.'; return; }
    state.hidden = true;
    tasksEl.innerHTML = filtered.map(task => `<article class="task" data-task-id="${text(task.id)}"><h2 class="task-title">${text(task.title || 'بدون عنوان')}</h2><div class="task-meta">${task.status ? `<span class="badge">${text(task.status)}</span>` : ''}${task.priority ? `<span class="badge">اولویت: ${text(task.priority)}</span>` : ''}${task.deadline ? `<span>مهلت: ${text(task.deadline)}</span>` : ''}${task.category ? `<span>دسته: ${text(task.category)}</span>` : ''}</div></article>`).join('');
    tasksEl.querySelectorAll('[data-task-id]').forEach(card => card.addEventListener('click', () => { window.location.href = `/static/task.html?id=${encodeURIComponent(card.dataset.taskId)}&bot_key=${encodeURIComponent(botKey)}`; }));
  }
  async function load() {
    state.hidden = false; state.textContent = 'در حال دریافت وظایف...';
    try { const response = await fetch(apiUrl('/api/tasks'), { headers }); if (!response.ok) throw new Error(`HTTP ${response.status}`); const data = await response.json(); tasks = Array.isArray(data.tasks) ? data.tasks : []; render(); }
    catch (error) { tasksEl.innerHTML = ''; state.hidden = false; state.textContent = 'دریافت وظایف انجام نشد.'; console.error(error); }
  }
  searchEl.addEventListener('input', render); statusEl.addEventListener('change', render); refreshEl.addEventListener('click', load); load();
})();
