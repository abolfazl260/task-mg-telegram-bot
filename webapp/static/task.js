(() => {
  const tg = window.Telegram?.WebApp;
  if (tg) { tg.ready(); tg.expand(); }

  const params = new URLSearchParams(window.location.search);
  const id = params.get('id');
  const botKey = params.get('bot_key') || '';
  const titleEl = document.getElementById('task-title');
  const taskEl = document.getElementById('task');
  const stateEl = document.getElementById('state');
  const backEl = document.getElementById('back');
  const headers = tg?.initData ? { 'X-Telegram-Init-Data': tg.initData } : {};
  const apiUrl = (path) => `${path}?bot_key=${encodeURIComponent(botKey)}`;

  function text(value) {
    return String(value ?? '').replace(/[&<>\"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#039;'}[ch]));
  }

  backEl.addEventListener('click', () => {
    window.location.href = `/?bot_key=${encodeURIComponent(botKey)}`;
  });

  async function load() {
    if (!id || !botKey) { stateEl.textContent = 'اطلاعات لازم برای دریافت وظیفه مشخص نشده است.'; return; }
    try {
      const response = await fetch(apiUrl(`/api/tasks/${encodeURIComponent(id)}`), { headers });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      const task = data.task;
      if (!task) throw new Error('Task not found');
      titleEl.textContent = task.title || 'وظیفه';
      taskEl.innerHTML = `<h2 class="task-title">${text(task.title || 'بدون عنوان')}</h2>${task.description ? `<p>${text(task.description)}</p>` : ''}<div class="task-meta">${task.status ? `<span class="badge">وضعیت: ${text(task.status)}</span>` : ''}${task.priority ? `<span class="badge">اولویت: ${text(task.priority)}</span>` : ''}${task.deadline ? `<span>مهلت: ${text(task.deadline)}</span>` : ''}${task.category ? `<span>دسته: ${text(task.category)}</span>` : ''}</div>`;
      taskEl.hidden = false;
      stateEl.hidden = true;
    } catch (error) {
      stateEl.textContent = 'دریافت جزئیات وظیفه انجام نشد.';
      console.error(error);
    }
  }
  load();
})();
