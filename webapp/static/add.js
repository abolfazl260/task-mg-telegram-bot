(() => {
  const tg = window.Telegram?.WebApp;
  if (tg) { tg.ready(); tg.expand(); }
  const form = document.getElementById('task-form');
  const state = document.getElementById('state');
  const headers = { 'Content-Type': 'application/json', ...(tg?.initData ? { 'X-Telegram-Init-Data': tg.initData } : {}) };
  document.getElementById('back').addEventListener('click', () => window.location.href = '/');
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    state.hidden = false; state.textContent = 'در حال ایجاد وظیفه...';
    const payload = {
      title: document.getElementById('title').value.trim(),
      description: document.getElementById('description').value.trim(),
      priority: document.getElementById('priority').value,
      deadline: document.getElementById('deadline').value || null,
      category: document.getElementById('category').value.trim() || null,
      tags: document.getElementById('tags').value.split(',').map(v => v.trim()).filter(Boolean),
    };
    try {
      const response = await fetch('/api/tasks', { method: 'POST', headers, body: JSON.stringify(payload) });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      state.textContent = 'وظیفه با موفقیت ایجاد شد.';
      const data = await response.json();
      if (data.task?.id) window.setTimeout(() => { window.location.href = `/static/task.html?id=${encodeURIComponent(data.task.id)}`; }, 250);
    } catch (error) {
      state.textContent = 'ایجاد وظیفه انجام نشد.';
      console.error(error);
    }
  });
})();
