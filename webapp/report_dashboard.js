(() => {
  const stateKey = 'task-report-dashboard-filter';
  let state = (() => { try { return JSON.parse(sessionStorage.getItem(stateKey) || '{}'); } catch { return {}; } })();
  state.period = state.period || 'month'; state.start = state.start || ''; state.end = state.end || ''; state.search = state.search || '';

  const params = () => {
    const p = new URLSearchParams({ period: state.period });
    if (state.start) p.set('start', state.start);
    if (state.end) p.set('end', state.end);
    if (state.search) p.set('search', state.search);
    return p.toString();
  };
  const save = () => sessionStorage.setItem(stateKey, JSON.stringify(state));
  const filteredUrl = (section = '', page = 1) => {
    const suffix = section ? `/section/${encodeURIComponent(section)}` : '';
    const p = new URLSearchParams(params());
    if (page > 1) p.set('page', page);
    return `/api/public-reports/monthly/${encodeURIComponent(token)}${suffix}?${p.toString()}`;
  };
  const filterCard = () => `
    <section id="reportFilters" class="card" style="margin-top:16px">
      <div class="section-title"><div><h2>🗓️ فیلتر گزارشات</h2><span class="muted">تمام KPIها، نمودارها و جدول از این بازه تبعیت می‌کنند.</span></div></div>
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:9px">
        <button class="filter-period ${state.period === 'today' ? 'active' : ''}" data-period="today">امروز</button>
        <button class="filter-period ${state.period === 'week' ? 'active' : ''}" data-period="week">این هفته</button>
        <button class="filter-period ${state.period === 'month' ? 'active' : ''}" data-period="month">این ماه</button>
        <button class="filter-period ${state.period === 'custom' ? 'active' : ''}" data-period="custom">سفارشی</button>
      </div>
      <div id="customDates" style="display:${state.period === 'custom' ? 'grid' : 'none'};grid-template-columns:1fr 1fr;gap:9px;margin-top:10px">
        <label class="muted">از تاریخ<input id="filterStart" type="date" value="${esc(state.start)}" style="display:block;width:100%;padding:10px;border:1px solid #e5eaf2;border-radius:12px;font:inherit"></label>
        <label class="muted">تا تاریخ<input id="filterEnd" type="date" value="${esc(state.end)}" style="display:block;width:100%;padding:10px;border:1px solid #e5eaf2;border-radius:12px;font:inherit"></label>
      </div>
      <div style="display:flex;gap:9px;margin-top:10px;flex-wrap:wrap">
        <input id="taskSearch" value="${esc(state.search)}" placeholder="🔍 جستجو در وظایف: عنوان، شناسه، دسته‌بندی، وضعیت" style="flex:1;min-width:240px;padding:11px 13px;border:1px solid #e5eaf2;border-radius:14px;font:inherit">
        <button id="applyReportFilter" style="border:1px solid #172033;background:#172033;color:#fff;border-radius:14px;padding:11px 16px;cursor:pointer;font:inherit;font-weight:800">اعمال فیلتر</button>
        <button id="exportCsv" style="border:1px solid #e5eaf2;background:#f8fafc;border-radius:14px;padding:11px 14px;cursor:pointer;font:inherit;font-weight:800">⬇️ CSV</button>
        <button id="exportPdf" style="border:1px solid #e5eaf2;background:#f8fafc;border-radius:14px;padding:11px 14px;cursor:pointer;font:inherit;font-weight:800">⬇️ PDF</button>
      </div>
    </section>`;

  function pie(data) {
    const rows = data || [];
    const total = rows.reduce((s, x) => s + Number(x.count || 0), 0);
    if (!total) return '<div class="empty">داده‌ای برای نمودار وضعیت وجود ندارد.</div>';
    const colors = ['#10b981', '#f59e0b', '#94a3b8', '#ef4444'];
    let cursor = 0;
    const parts = rows.map((x, i) => { const n = Number(x.count || 0); const a = cursor; cursor += n / total * 360; return `${colors[i % colors.length]} ${a}deg ${cursor}deg`; }).join(',');
    return `<div style="display:grid;grid-template-columns:220px 1fr;gap:22px;align-items:center;max-width:620px">
      <div style="width:190px;height:190px;border-radius:50%;background:conic-gradient(${parts});position:relative"><div style="position:absolute;inset:48px;border-radius:50%;background:#fff;display:grid;place-items:center;font-weight:900">${total}</div></div>
      <div>${rows.map((x,i)=>`<div style="display:flex;align-items:center;gap:8px;margin:9px 0"><i style="width:12px;height:12px;border-radius:4px;background:${colors[i % colors.length]}"></i><span>${esc(x.label)}</span><b style="margin-right:auto">${x.count}</b></div>`).join('')}</div>
    </div>`;
  }

  async function downloadExport(format) {
    const r = await fetch(`/api/public-reports/monthly/${encodeURIComponent(token)}/export/${format}?${params()}`, { cache: 'no-store' });
    if (!r.ok) throw new Error('خطا در ایجاد خروجی گزارش');
    const blob = await r.blob();
    const url = URL.createObjectURL(blob); const a = document.createElement('a');
    a.href = url; a.download = `task-report.${format}`; a.click(); URL.revokeObjectURL(url);
  }

  function bindFilters() {
    document.querySelectorAll('.filter-period').forEach(button => button.addEventListener('click', () => {
      state.period = button.dataset.period;
      document.querySelectorAll('.filter-period').forEach(x => x.classList.toggle('active', x === button));
      document.getElementById('customDates').style.display = state.period === 'custom' ? 'grid' : 'none';
      save();
      loadSummary();
    }));
    document.getElementById('applyReportFilter')?.addEventListener('click', () => {
      state.search = document.getElementById('taskSearch')?.value.trim() || '';
      state.start = document.getElementById('filterStart')?.value || '';
      state.end = document.getElementById('filterEnd')?.value || '';
      save(); loadSummary();
      if (window.activeReportSection) loadSection(window.activeReportSection, 1);
    });
    ['filterStart', 'filterEnd'].forEach(id => document.getElementById(id)?.addEventListener('change', () => {
      state.start = document.getElementById('filterStart')?.value || ''; state.end = document.getElementById('filterEnd')?.value || ''; save();
    }));
    document.getElementById('exportCsv')?.addEventListener('click', () => downloadExport('csv').catch(e => alert(e.message)));
    document.getElementById('exportPdf')?.addEventListener('click', () => downloadExport('pdf').catch(e => alert(e.message)));
  }

  const originalLoadSection = window.loadSection;
  window.loadSection = async function(section, page = 1) {
    window.activeReportSection = section;
    details.innerHTML = '<div class="loading">در حال دریافت گزارش...</div>';
    document.querySelectorAll('[data-section]').forEach(b => b.classList.toggle('active', b.dataset.section === section));
    try {
      const data = await getJson(filteredUrl(section, page));
      if (section === 'status') {
        details.innerHTML = `<div class="section-title"><h2>📌 وضعیت وظایف</h2><span class="muted">بر اساس فیلتر انتخاب‌شده</span></div><div style="margin-top:10px">${pie(data.rows)}</div>`;
        return;
      }
      return originalLoadSection.call(this, section, page);
    } catch (e) { details.innerHTML = `<p class="error">${esc(e.message)}</p>`; }
  };

  window.loadSummary = async function() {
    try {
      const data = await getJson(filteredUrl());
      const s = data.summary || {};
      const t = trend(s.total_change);
      app.innerHTML = `<div class="hero-top"><div><h1>📊 گزارش تحت وب</h1><p>${esc(data.period?.gregorian || '')} · ${esc(data.period?.jalali || '')}</p></div><div class="badge">گزارش شخصی و اختصاصی</div></div><div class="stats">${stat(s.total||0,'کل وظایف',t)}${stat(s.done||0,'انجام‌شده')}${stat(s.in_progress||0,'در حال انجام')}${stat(s.pending||0,'شروع‌نشده')}${stat(s.cancelled||0,'لغوشده')}${stat((s.completion_rate||0)+'٪','نرخ انجام')}${stat(s.average_completion_days == null ? '—' : s.average_completion_days+' روز','⏱️ میانگین تکمیل')}${stat(s.overdue||0,'عقب‌افتاده')}${stat(s.with_deadline||0,'دارای مهلت')}</div>`;
      if (!document.getElementById('reportFilters')) priorityTop.insertAdjacentHTML('beforebegin', filterCard());
      bindFilters(); renderPriority(data);
      details.innerHTML = `<div class="section-title"><h2>📊 وضعیت وظایف</h2><span class="muted">برای مشاهده نمودار کامل روی «وضعیت‌ها» بزنید.</span></div>${pie(data.by_status)}`;
    } catch (e) { app.innerHTML = `<h1>گزارش تحت وب</h1><p class="error">${esc(e.message)}</p>`; }
  };

  save();
  window.loadSummary();
})();
