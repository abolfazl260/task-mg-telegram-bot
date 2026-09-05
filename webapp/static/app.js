(() => {
  const tg = window.Telegram?.WebApp;
  if (tg) { tg.ready(); tg.expand(); }

  const state = document.getElementById('state');
  const searchEl = document.getElementById('search');
  const statusEl = document.getElementById('status-filter');
  const priorityEl = document.getElementById('priority-filter');
  const refreshEl = document.getElementById('refresh');
  const themeToggleEl = document.getElementById('theme-toggle');
  const resultCountEl = document.getElementById('result-count');

  // Views
  const viewTabs = document.querySelectorAll('.notion-tab');
  const viewPanels = {
    table: document.getElementById('view-table'),
    board: document.getElementById('view-board'),
    analytics: document.getElementById('view-analytics')
  };
  let currentView = 'table';

  // Table & Board Containers
  const tableBody = document.getElementById('notion-table-body');
  const boardCards = {
    pending: document.getElementById('cards-pending'),
    in_progress: document.getElementById('cards-in_progress'),
    done: document.getElementById('cards-done'),
    cancelled: document.getElementById('cards-cancelled')
  };
  const boardCounts = {
    pending: document.getElementById('count-pending'),
    in_progress: document.getElementById('count-in_progress'),
    done: document.getElementById('count-done'),
    cancelled: document.getElementById('count-cancelled')
  };

  // Analytics
  const reportEl = document.getElementById('status-report');
  const priorityReportEl = document.getElementById('priority-report');

  // Modal elements
  const modal = document.getElementById('notion-modal');
  const modalForm = document.getElementById('notion-task-form');
  const modalClose = document.getElementById('modal-close');
  const modalCancel = document.getElementById('modal-cancel');
  const modalFullPage = document.getElementById('modal-full-page');
  const modalTaskId = document.getElementById('modal-task-id');
  const modalTitle = document.getElementById('modal-title');
  const modalStatus = document.getElementById('modal-status');
  const modalPriority = document.getElementById('modal-priority');
  const modalDeadline = document.getElementById('modal-deadline');
  const modalCategory = document.getElementById('modal-category');
  const modalTags = document.getElementById('modal-tags');
  const modalDescription = document.getElementById('modal-description');
  const modalError = document.getElementById('modal-error');
  const modalSaveBtn = document.getElementById('modal-save');

  // Add buttons
  const btnTopNew = document.getElementById('btn-new-task-top');
  const btnQuickNew = document.getElementById('btn-quick-new');
  const btnTableAdd = document.getElementById('btn-table-add');

  let tasks = [];
  const pageParams = new URLSearchParams(window.location.search);
  const botKey = pageParams.get('bot_key') || window.__dashboardTaskToken || '';
  const initData = tg?.initData || '';
  const headers = {
    'Content-Type': 'application/json',
    ...(initData ? { 'X-Telegram-Init-Data': initData } : {})
  };

  const apiUrl = (path) => `${path}?bot_key=${encodeURIComponent(botKey)}`;

  function esc(val) {
    return String(val ?? '').replace(/[&<>"']/g, ch => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
    }[ch]));
  }

  const statusMap = {
    pending: { label: 'در انتظار', class: 'status-pending' },
    in_progress: { label: 'در حال انجام', class: 'status-in_progress' },
    done: { label: 'انجام‌شده', class: 'status-done' },
    cancelled: { label: 'لغوشده', class: 'status-cancelled' }
  };

  const priorityMap = {
    low: { label: 'کم', class: 'priority-low' },
    medium: { label: 'متوسط', class: 'priority-medium' },
    high: { label: 'زیاد', class: 'priority-high' },
    urgent: { label: 'فوری', class: 'priority-urgent' }
  };

  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('task-dashboard-theme', theme);
    themeToggleEl.textContent = theme === 'dark' ? '☀' : '☾';
    themeToggleEl.setAttribute('aria-label', theme === 'dark' ? 'حالت روشن' : 'حالت تاریک');
  }

  function initTheme() {
    const saved = localStorage.getItem('task-dashboard-theme');
    const telegramTheme = tg?.colorScheme === 'dark' ? 'dark' : 'light';
    applyTheme(saved || telegramTheme);
  }

  function switchView(viewName) {
    currentView = viewName;
    viewTabs.forEach(tab => {
      tab.classList.toggle('active', tab.dataset.view === viewName);
    });
    Object.entries(viewPanels).forEach(([name, el]) => {
      if (el) el.hidden = name !== viewName;
    });
  }

  function filteredTasks() {
    const q = (searchEl?.value || '').trim().toLowerCase();
    const st = statusEl?.value || '';
    const pr = priorityEl?.value || '';

    return tasks.filter(t => {
      const haystack = `${t.title || ''} ${t.description || ''} ${t.category || ''} ${t.tags || ''}`.toLowerCase();
      const matchQ = !q || haystack.includes(q);
      const matchSt = !st || t.status === st;
      const matchPr = !pr || String(t.priority || 'medium').toLowerCase() === pr;
      return matchQ && matchSt && matchPr;
    });
  }

  function renderTable(list) {
    if (!tableBody) return;
    if (!list.length) {
      tableBody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:28px;color:var(--text-secondary)">هیچ وظیفه‌ای برای نمایش پیدا نشد.</td></tr>`;
      return;
    }

    tableBody.innerHTML = list.map(t => {
      const st = statusMap[t.status] || { label: t.status || '—', class: 'status-pending' };
      const pr = priorityMap[String(t.priority || 'medium').toLowerCase()] || { label: t.priority || '—', class: 'priority-medium' };
      const isDone = t.status === 'done';
      const deadline = t.deadline ? t.deadline.replace('T', ' ').slice(0, 16) : '—';

      return `
        <tr data-id="${esc(t.id)}">
          <td class="col-check">
            <input type="checkbox" class="notion-checkbox" ${isDone ? 'checked' : ''} data-toggle-id="${esc(t.id)}">
          </td>
          <td class="col-title" data-open-id="${esc(t.id)}" style="${isDone ? 'text-decoration:line-through;opacity:0.6' : ''}">
            ${esc(t.title || 'بدون عنوان')}
          </td>
          <td>
            <span class="notion-pill ${st.class}">${st.label}</span>
          </td>
          <td>
            <span class="notion-pill ${pr.class}">${pr.label}</span>
          </td>
          <td style="color:var(--text-secondary);font-size:12px;direction:ltr;text-align:right">
            ${deadline !== '—' ? '⏰ ' + esc(deadline) : '—'}
          </td>
          <td>
            ${t.category ? `<span class="notion-pill category-pill">${esc(t.category)}</span>` : '—'}
          </td>
          <td>
            ${t.tags ? `<span class="notion-pill tag-pill">${esc(t.tags)}</span>` : '—'}
          </td>
          <td class="col-actions">
            <button class="notion-btn" style="height:26px;padding:0 8px;font-size:11px" data-open-id="${esc(t.id)}">✏️ ویرایش</button>
          </td>
        </tr>
      `;
    }).join('');
  }

  function renderBoard(list) {
    const cols = { pending: [], in_progress: [], done: [], cancelled: [] };
    list.forEach(t => {
      const s = t.status in cols ? t.status : 'pending';
      cols[s].push(t);
    });

    Object.entries(cols).forEach(([s, colTasks]) => {
      if (boardCounts[s]) boardCounts[s].textContent = colTasks.length;
      if (!boardCards[s]) return;

      if (!colTasks.length) {
        boardCards[s].innerHTML = '<div style="font-size:12px;color:var(--text-secondary);padding:14px;text-align:center">موردی نیست</div>';
        return;
      }

      boardCards[s].innerHTML = colTasks.map(t => {
        const pr = priorityMap[String(t.priority || 'medium').toLowerCase()] || { label: t.priority, class: 'priority-medium' };
        const dl = t.deadline ? t.deadline.replace('T', ' ').slice(0, 16) : '';

        return `
          <div class="notion-card" data-open-id="${esc(t.id)}">
            <div class="notion-card-title">${esc(t.title || 'بدون عنوان')}</div>
            <div class="notion-card-meta">
              <span class="notion-pill ${pr.class}">${pr.label}</span>
              ${t.category ? `<span class="notion-pill category-pill">${esc(t.category)}</span>` : ''}
              ${dl ? `<span style="font-size:11px">⏰ ${esc(dl)}</span>` : ''}
            </div>
          </div>
        `;
      }).join('');
    });
  }

  function renderAnalytics(list) {
    if (!reportEl || !priorityReportEl) return;
    const total = list.length;
    if (!total) {
      reportEl.innerHTML = '<div style="color:var(--text-secondary);text-align:center;padding:20px">داده‌ای برای گزارش وجود ندارد.</div>';
      priorityReportEl.innerHTML = '<div style="color:var(--text-secondary);text-align:center;padding:20px">داده‌ای برای گزارش وجود ندارد.</div>';
      return;
    }

    // Status distribution
    const statuses = ['pending', 'in_progress', 'done', 'cancelled'].map(st => ({
      status: st,
      count: list.filter(t => t.status === st).length
    }));
    reportEl.innerHTML = `
      <div style="display:flex;flex-direction:column;gap:8px">
        ${statuses.map(item => {
          const pct = Math.round((item.count / total) * 100);
          const meta = statusMap[item.status] || { label: item.status };
          return `
            <div style="display:flex;align-items:center;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border-light);font-size:13px">
              <span class="notion-pill ${meta.class}">${meta.label}</span>
              <div style="display:flex;gap:12px;align-items:center">
                <strong>${item.count}</strong>
                <small style="color:var(--text-secondary);min-width:36px">${pct}٪</small>
              </div>
            </div>
          `;
        }).join('')}
      </div>
    `;

    // Priority distribution
    const priorities = ['urgent', 'high', 'medium', 'low'].map(pr => ({
      priority: pr,
      count: list.filter(t => String(t.priority || 'medium').toLowerCase() === pr).length
    }));
    priorityReportEl.innerHTML = `
      <div style="display:flex;flex-direction:column;gap:8px">
        ${priorities.map(item => {
          const pct = Math.round((item.count / total) * 100);
          const meta = priorityMap[item.priority] || { label: item.priority };
          return `
            <div style="display:flex;align-items:center;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border-light);font-size:13px">
              <span class="notion-pill ${meta.class}">${meta.label}</span>
              <div style="display:flex;gap:12px;align-items:center">
                <strong>${item.count}</strong>
                <small style="color:var(--text-secondary);min-width:36px">${pct}٪</small>
              </div>
            </div>
          `;
        }).join('')}
      </div>
    `;
  }

  function render() {
    const list = filteredTasks();
    if (resultCountEl) resultCountEl.textContent = `${list.length} وظیفه`;
    renderTable(list);
    renderBoard(list);
    renderAnalytics(list);
  }

  // Modal handling
  function openModal(task = null, defaultStatus = 'pending') {
    modalError.hidden = true;
    modalError.textContent = '';

    if (task) {
      modalTaskId.value = task.id;
      modalTitle.value = task.title || '';
      modalStatus.value = task.status || 'pending';
      modalPriority.value = (task.priority || 'medium').toLowerCase();
      modalDeadline.value = (task.deadline || '').replace(' ', 'T').slice(0, 16);
      modalCategory.value = task.category || '';
      modalTags.value = task.tags || '';
      modalDescription.value = task.description || '';
      modalSaveBtn.textContent = 'ذخیره تغییرات';
      if (modalFullPage) {
        modalFullPage.href = `/task/${encodeURIComponent(task.id)}?bot_key=${encodeURIComponent(botKey)}`;
        modalFullPage.hidden = false;
      }
    } else {
      modalTaskId.value = '';
      modalTitle.value = '';
      modalStatus.value = defaultStatus;
      modalPriority.value = 'medium';
      modalDeadline.value = '';
      modalCategory.value = '';
      modalTags.value = '';
      modalDescription.value = '';
      modalSaveBtn.textContent = 'ایجاد وظیفه';
      if (modalFullPage) {
        modalFullPage.hidden = true;
      }
    }
    modal.hidden = false;
    setTimeout(() => modalTitle.focus(), 50);
  }

  function closeModal() {
    modal.hidden = true;
  }

  async function handleModalSubmit(e) {
    e.preventDefault();
    const id = modalTaskId.value.trim();
    const payload = {
      title: modalTitle.value.trim(),
      status: modalStatus.value,
      priority: modalPriority.value,
      deadline: modalDeadline.value,
      category: modalCategory.value.trim(),
      tags: modalTags.value.trim(),
      description: modalDescription.value.trim()
    };

    if (!payload.title) {
      modalError.hidden = false;
      modalError.textContent = 'عنوان وظیفه نمی‌تواند خالی باشد.';
      return;
    }

    modalSaveBtn.disabled = true;
    modalSaveBtn.textContent = 'در حال ذخیره...';

    try {
      const url = id ? apiUrl(`/api/tasks/${encodeURIComponent(id)}`) : apiUrl('/api/tasks');
      const method = id ? 'PATCH' : 'POST';
      const res = await fetch(url, {
        method,
        headers,
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error(`خطای سرور: ${res.status}`);
      closeModal();
      await load();
    } catch (err) {
      modalError.hidden = false;
      modalError.textContent = err.message || 'خطا در ذخیره وظیفه';
    } finally {
      modalSaveBtn.disabled = false;
      modalSaveBtn.textContent = id ? 'ذخیره تغییرات' : 'ایجاد وظیفه';
    }
  }

  async function toggleTaskDone(id, isChecked) {
    const newStatus = isChecked ? 'done' : 'pending';
    try {
      const res = await fetch(apiUrl(`/api/tasks/${encodeURIComponent(id)}`), {
        method: 'PATCH',
        headers,
        body: JSON.stringify({ status: newStatus })
      });
      if (!res.ok) throw new Error('Failed to update status');
      const t = tasks.find(x => String(x.id) === String(id));
      if (t) t.status = newStatus;
      render();
    } catch (err) {
      console.error(err);
      load();
    }
  }

  async function load() {
    if (state) { state.hidden = false; state.textContent = 'در حال بارگذاری وظایف...'; }
    try {
      const res = await fetch(apiUrl('/api/tasks'), { headers, cache: 'no-store' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      tasks = Array.isArray(data.tasks) ? data.tasks : [];
      if (state) state.hidden = true;
      render();
    } catch (err) {
      if (state) {
        state.hidden = false;
        state.textContent = 'خطا در دریافت اطلاعات وظایف.';
      }
      console.error(err);
    }
  }

  // Bind Events
  viewTabs.forEach(tab => {
    tab.addEventListener('click', () => switchView(tab.dataset.view));
  });

  searchEl?.addEventListener('input', render);
  statusEl?.addEventListener('change', render);
  priorityEl?.addEventListener('change', render);
  refreshEl?.addEventListener('click', load);

  themeToggleEl?.addEventListener('click', () => {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    applyTheme(next);
  });

  // Modal open buttons
  btnTopNew?.addEventListener('click', () => openModal(null));
  btnQuickNew?.addEventListener('click', () => openModal(null));
  btnTableAdd?.addEventListener('click', () => openModal(null));

  document.querySelectorAll('[data-add-status]').forEach(btn => {
    btn.addEventListener('click', () => openModal(null, btn.dataset.addStatus));
  });

  // Click delegation for opening tasks or checkboxes
  document.addEventListener('click', e => {
    const openBtn = e.target.closest('[data-open-id]');
    if (openBtn) {
      e.preventDefault();
      const tid = openBtn.dataset.openId;
      const t = tasks.find(x => String(x.id) === String(tid));
      if (t) openModal(t);
      return;
    }

    const chk = e.target.closest('[data-toggle-id]');
    if (chk) {
      toggleTaskDone(chk.dataset.toggleId, chk.checked);
    }
  });

  modalClose?.addEventListener('click', closeModal);
  modalCancel?.addEventListener('click', closeModal);
  modal?.addEventListener('click', e => {
    if (e.target === modal) closeModal();
  });
  modalForm?.addEventListener('submit', handleModalSubmit);

  initTheme();
  load();
})();