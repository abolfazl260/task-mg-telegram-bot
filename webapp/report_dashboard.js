(() => {
  const style = document.createElement('style');
  style.textContent = `
#reportFilters{margin-top:16px!important;padding:22px!important;border-radius:24px!important;border:1px solid #e4e9f2!important;box-shadow:0 14px 38px rgba(15,23,42,.07)!important;background:linear-gradient(180deg,#fff,#fbfcfe)!important}
#reportFilters .section-title{margin-bottom:18px!important;align-items:flex-start!important}
#reportFilters .section-title h2{font-size:20px!important;letter-spacing:-.2px}
#reportFilters .section-title .muted{display:block;margin-top:5px;line-height:1.7}
#clearReportFilters{border:1px solid #e2e8f0!important;background:#fff!important;color:#475569!important;border-radius:12px!important;padding:9px 14px!important;transition:.18s!important}
#clearReportFilters:hover{background:#f8fafc!important;border-color:#cbd5e1!important;transform:translateY(-1px)}
#reportFilters>div:nth-of-type(2){display:grid!important;grid-template-columns:repeat(4,1fr)!important;gap:8px!important;padding:5px!important;background:#f1f5f9!important;border-radius:16px!important}
#reportFilters .filter-period{border:0!important;background:transparent!important;color:#64748b!important;border-radius:12px!important;padding:11px 10px!important;cursor:pointer!important;font:inherit!important;font-weight:800!important;transition:.18s!important}
#reportFilters .filter-period:hover{background:#fff!important;color:#172033!important}
#reportFilters .filter-period.active{background:#172033!important;color:#fff!important;box-shadow:0 5px 14px rgba(15,23,42,.18)!important}
#customDates{grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:12px!important;margin-top:12px!important;padding:13px!important;border:1px dashed #d7dee9!important;border-radius:16px!important;background:#f8fafc!important}
#reportFilters label.muted{display:block!important;color:#64748b!important;font-size:12px!important;font-weight:700!important;line-height:1.8!important}
#reportFilters select,#reportFilters input{display:block!important;width:100%!important;margin-top:5px!important;min-height:44px!important;padding:10px 12px!important;border:1px solid #dfe5ee!important;border-radius:13px!important;background:#fff!important;color:#172033!important;font:inherit!important;outline:0!important;transition:border-color .18s,box-shadow .18s,background .18s!important}
#reportFilters select:hover,#reportFilters input:hover{border-color:#c8d1df!important}
#reportFilters select:focus,#reportFilters input:focus{border-color:#64748b!important;box-shadow:0 0 0 4px rgba(100,116,139,.11)!important;background:#fff!important}
#reportFilters>div:nth-of-type(4){display:grid!important;grid-template-columns:repeat(3,minmax(0,1fr))!important;gap:12px!important;margin-top:12px!important}
#reportFilters>div:last-child{display:grid!important;grid-template-columns:minmax(220px,1.8fr) minmax(180px,1fr) auto auto auto!important;gap:10px!important;margin-top:14px!important;align-items:end!important}
#taskSearch{min-width:0!important}
#reportFilters #applyReportFilter,#reportFilters #exportCsv,#reportFilters #exportPdf{min-height:44px!important;white-space:nowrap!important;border-radius:13px!important;padding:10px 15px!important;font:inherit!important;font-weight:800!important;cursor:pointer!important;transition:.18s!important}
#reportFilters #applyReportFilter{border:1px solid #172033!important;background:#172033!important;color:#fff!important;box-shadow:0 7px 16px rgba(15,23,42,.16)!important}
#reportFilters #applyReportFilter:hover{background:#263653!important;transform:translateY(-1px);box-shadow:0 9px 20px rgba(15,23,42,.2)!important}
#reportFilters #exportCsv,#reportFilters #exportPdf{border:1px solid #e2e8f0!important;background:#fff!important;color:#334155!important}
#reportFilters #exportCsv:hover,#reportFilters #exportPdf:hover{background:#f8fafc!important;border-color:#cbd5e1!important;transform:translateY(-1px)}
#priorityTop{padding:22px!important;border-radius:24px!important;border:1px solid #e4e9f2!important;box-shadow:0 14px 38px rgba(15,23,42,.06)!important;background:#fff!important}
#priorityTop .section-title{margin-bottom:16px!important}
#priorityTop .section-title h2{font-size:20px!important}
#priorityTop .priority-summary{display:grid!important;grid-template-columns:repeat(3,minmax(0,1fr))!important;gap:14px!important}
.priority-box{position:relative!important;overflow:hidden!important;min-height:112px!important;padding:18px 19px!important;border-radius:18px!important;border:1px solid transparent!important;display:flex!important;flex-direction:column!important;justify-content:center!important;transition:transform .18s,box-shadow .18s!important}
.priority-box:hover{transform:translateY(-2px)!important;box-shadow:0 10px 24px rgba(15,23,42,.08)!important}
.priority-box:before{content:"";position:absolute;right:0;top:0;bottom:0;width:4px;border-radius:0 18px 18px 0}
.priority-box.high{background:linear-gradient(135deg,#fff8f7,#fff1f0)!important;border-color:#fee2e2!important}
.priority-box.high:before{background:#ef4444}
.priority-box.medium{background:linear-gradient(135deg,#fffaf1,#fff7e8)!important;border-color:#fde7c2!important}
.priority-box.medium:before{background:#f59e0b}
.priority-box.low{background:linear-gradient(135deg,#f5fcf8,#ecfdf3)!important;border-color:#d8f3e4!important}
.priority-box.low:before{background:#10b981}
.priority-box .name{font-size:13px!important;font-weight:800!important}
.priority-box strong{font-size:32px!important;line-height:1.1!important;margin-top:9px!important;letter-spacing:-.5px}
.priority-box.high .name{color:#b42318!important}
.priority-box.medium .name{color:#b54708!important}
.priority-box.low .name{color:#027a48!important}

/* Productivity Metrics Styles */
#productivityCard{padding:22px!important;border-radius:24px!important;border:1px solid #e4e9f2!important;box-shadow:0 14px 38px rgba(15,23,42,.06)!important;background:#fff!important;margin-top:16px!important}
.productivity-grid{display:grid!important;grid-template-columns:repeat(4,minmax(0,1fr))!important;gap:14px!important;margin-top:14px!important}
.prod-metric-box{position:relative!important;background:#f8fafc!important;border:1px solid #e2e8f0!important;border-radius:18px!important;padding:16px 18px!important;display:flex!important;flex-direction:column!important;justify-content:center!important;transition:transform .18s,box-shadow .18s!important}
.prod-metric-box:hover{transform:translateY(-2px)!important;box-shadow:0 10px 24px rgba(15,23,42,.08)!important;background:#fff!important}
.prod-metric-box:before{content:"";position:absolute;right:0;top:0;bottom:0;width:4px;border-radius:0 18px 18px 0}
.prod-metric-box.lead-time:before{background:#6366f1}
.prod-metric-box.on-time:before{background:#10b981}
.prod-metric-box.overdue-rate:before{background:#ef4444}
.prod-metric-box.open-status:before{background:#f59e0b}
.p-title{font-size:13px!important;font-weight:800!important;color:#475569!important}
.p-value{font-size:26px!important;font-weight:900!important;line-height:1.2!important;margin:8px 0 4px!important;letter-spacing:-.4px}
.p-sub{font-size:11px!important;color:#94a3b8!important;line-height:1.5!important}

/* Jalali GitHub Contribution Heatmap */
.gh-heatmap-wrapper{margin-top:18px!important;padding:20px!important;background:#f8fafc!important;border:1px solid #e2e8f0!important;border-radius:20px!important;overflow-x:auto!important}
.gh-heatmap-container{display:flex!important;gap:10px!important;align-items:flex-start!important;min-width:640px!important}
.gh-day-labels{display:grid!important;grid-template-rows:repeat(7,16px)!important;gap:4px!important;font-size:11px!important;color:#64748b!important;font-weight:700!important;line-height:16px!important;text-align:right!important;padding-left:4px!important}
.gh-cells-grid{display:grid!important;grid-template-rows:repeat(7,16px)!important;grid-auto-flow:column!important;grid-auto-columns:16px!important;gap:4px!important}
.gh-heat-cell{width:16px!important;height:16px!important;border-radius:4px!important;cursor:pointer!important;transition:transform .14s,outline .14s!important;box-sizing:border-box!important}
.gh-heat-cell:hover{transform:scale(1.3)!important;z-index:3!important;outline:2px solid #1e293b!important}
.gh-level-0{background:#ebedf0!important;border:1px solid rgba(27,31,35,.05)!important}
.gh-level-1{background:#9be9a8!important;border:1px solid rgba(27,31,35,.08)!important}
.gh-level-2{background:#40c463!important;border:1px solid rgba(27,31,35,.08)!important}
.gh-level-3{background:#30a14e!important;border:1px solid rgba(27,31,35,.08)!important}
.gh-level-4{background:#216e39!important;border:1px solid rgba(27,31,35,.08)!important}
.gh-legend{display:flex!important;align-items:center!important;gap:6px!important;justify-content:flex-end!important;margin-top:16px!important;font-size:12px!important;color:#64748b!important}
.gh-legend .gh-heat-cell{width:14px!important;height:14px!important}
.busiest-banner{background:#fff!important;border:1px solid #e2e8f0!important;border-radius:16px!important;padding:14px 18px!important;margin-top:14px!important;display:flex!important;flex-direction:column!important;gap:10px!important}
.busiest-list{display:flex!important;flex-wrap:wrap!important;gap:8px!important}
.busy-pill{background:#f1f5f9!important;border:1px solid #cbd5e1!important;border-radius:999px!important;padding:5px 12px!important;font-size:12px!important;color:#1e293b!important}

@media(max-width:900px){
  #reportFilters>div:nth-of-type(4){grid-template-columns:repeat(2,minmax(0,1fr))!important}
  #reportFilters>div:last-child{grid-template-columns:1fr 1fr!important}
  #reportFilters #taskSearch{grid-column:1/-1}
  #reportFilters #taskSort{grid-column:auto}
  #priorityTop .priority-summary{grid-template-columns:1fr!important}
  .productivity-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important}
}
@media(max-width:600px){
  #reportFilters,#priorityTop,#productivityCard{padding:16px!important;border-radius:20px!important}
  #reportFilters .section-title{gap:10px!important}
  #reportFilters .section-title h2,#priorityTop .section-title h2{font-size:18px!important}
  #reportFilters>div:nth-of-type(2){grid-template-columns:repeat(2,1fr)!important}
  #customDates{grid-template-columns:1fr!important}
  #reportFilters>div:nth-of-type(4){grid-template-columns:1fr!important}
  #reportFilters>div:last-child{grid-template-columns:1fr!important;align-items:stretch!important}
  #reportFilters #taskSearch,#reportFilters #taskSort{grid-column:auto!important}
  #reportFilters #applyReportFilter,#reportFilters #exportCsv,#reportFilters #exportPdf{width:100%!important}
  #priorityTop .priority-summary{grid-template-columns:1fr!important}
  .priority-box{min-height:96px!important;padding:15px 17px!important}
  .priority-box strong{font-size:28px!important}
  .productivity-grid{grid-template-columns:1fr!important}
}
`;
  document.head.appendChild(style);

  const stateKey = 'task-report-dashboard-filter';
  let state = (() => {
    try {
      return JSON.parse(sessionStorage.getItem(stateKey) || '{}');
    } catch {
      return {};
    }
  })();
  state.period = state.period || 'month';
  state.start = state.start || '';
  state.end = state.end || '';
  state.search = state.search || '';
  state.filters = state.filters || {
    status: '', priority: '', category: '', assignee: '', has_deadline: '', overdue: '', sort: 'newest'
  };
  state.filters.sort = state.filters.sort || 'newest';

  const params = () => {
    const p = new URLSearchParams({ period: state.period });
    if (state.start) p.set('start', state.start);
    if (state.end) p.set('end', state.end);
    const structured = { q: state.search, ...state.filters };
    if (Object.values(structured).some(Boolean)) p.set('search', JSON.stringify(structured));
    return p.toString();
  };
  const save = () => sessionStorage.setItem(stateKey, JSON.stringify(state));

  const filteredUrl = (section = '', page = 1) => {
    const suffix = section ? `/section/${encodeURIComponent(section)}` : '';
    const p = new URLSearchParams(params());
    if (page > 1) p.set('page', page);
    return `/api/public-reports/monthly/${encodeURIComponent(token)}${suffix}?${p.toString()}`;
  };

  const filterCard = (options = {}) => {
    const opt = (key, placeholder) =>
      `<option value="">${placeholder}</option>${(options[key] || [])
        .map(x => `<option value="${esc(x.value)}" ${state.filters[key] === x.value ? 'selected' : ''}>${esc(x.label)}</option>`)
        .join('')}`;
    return `<section id="reportFilters" class="card" style="margin-top:16px">
      <div class="section-title">
        <div>
          <h2>🗓️ فیلتر گزارشات</h2>
          <span class="muted">فیلترها مستقل هستند و می‌توانند هم‌زمان اعمال شوند.</span>
        </div>
        <button id="clearReportFilters" style="border:1px solid #e5eaf2;background:#f8fafc;border-radius:12px;padding:9px 12px;cursor:pointer;font:inherit;font-weight:700">پاک کردن</button>
      </div>
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
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin-top:10px">
        <label class="muted">وضعیت<select id="filterStatus" style="display:block;width:100%;padding:11px;border:1px solid #e5eaf2;border-radius:14px;background:#fff;font:inherit">${opt('status', 'همه وضعیت‌ها')}</select></label>
        <label class="muted">اولویت<select id="filterPriority" style="display:block;width:100%;padding:11px;border:1px solid #e5eaf2;border-radius:14px;background:#fff;font:inherit">${opt('priority', 'همه اولویت‌ها')}</select></label>
        <label class="muted">دسته‌بندی<select id="filterCategory" style="display:block;width:100%;padding:11px;border:1px solid #e5eaf2;border-radius:14px;background:#fff;font:inherit">${opt('category', 'همه دسته‌بندی‌ها')}</select></label>
        <label class="muted">مسئول<select id="filterAssignee" style="display:block;width:100%;padding:11px;border:1px solid #e5eaf2;border-radius:14px;background:#fff;font:inherit">${opt('assignee', 'همه مسئولین')}</select></label>
        <label class="muted">مهلت<select id="filterHasDeadline" style="display:block;width:100%;padding:11px;border:1px solid #e5eaf2;border-radius:14px;background:#fff;font:inherit">${opt('has_deadline', 'همه')}</select></label>
        <label class="muted">عقب‌افتادگی<select id="filterOverdue" style="display:block;width:100%;padding:11px;border:1px solid #e5eaf2;border-radius:14px;background:#fff;font:inherit">${opt('overdue', 'همه')}</select></label>
      </div>
      <div style="display:flex;gap:9px;margin-top:10px;flex-wrap:wrap">
        <input id="taskSearch" value="${esc(state.search)}" placeholder="🔍 جستجو: عنوان، شناسه، دسته‌بندی، وضعیت، اولویت، مسئول یا Tag" style="flex:1;min-width:240px;padding:11px 13px;border:1px solid #e5eaf2;border-radius:14px;font:inherit">
        <label class="muted" style="min-width:230px">مرتب‌سازی<select id="taskSort" style="display:block;width:100%;padding:11px;border:1px solid #e5eaf2;border-radius:14px;background:#fff;font:inherit">
          <option value="newest" ${state.filters.sort === 'newest' ? 'selected' : ''}>↓ جدیدترین</option>
          <option value="oldest" ${state.filters.sort === 'oldest' ? 'selected' : ''}>↑ قدیمی‌ترین</option>
          <option value="overdue" ${state.filters.sort === 'overdue' ? 'selected' : ''}>↓ بیشترین تأخیر</option>
          <option value="priority" ${state.filters.sort === 'priority' ? 'selected' : ''}>↓ بالاترین اولویت</option>
          <option value="duration" ${state.filters.sort === 'duration' ? 'selected' : ''}>↓ طولانی‌ترین زمان انجام</option>
        </select></label>
        <button id="applyReportFilter" style="border:1px solid #172033;background:#172033;color:#fff;border-radius:14px;padding:11px 16px;cursor:pointer;font:inherit;font-weight:800">اعمال فیلتر</button>
        <button id="exportCsv" style="border:1px solid #e5eaf2;background:#f8fafc;border-radius:14px;padding:11px 14px;cursor:pointer;font:inherit;font-weight:800">⬇️ CSV</button>
        <button id="exportPdf" style="border:1px solid #e5eaf2;background:#f8fafc;border-radius:14px;padding:11px 14px;cursor:pointer;font:inherit;font-weight:800">⬇️ PDF</button>
      </div>
    </section>`;
  };

  function priority(p) {
    const k = (p || '').toLowerCase(),
      c = k === 'high' ? 'priority-high' : k === 'low' ? 'priority-low' : 'priority-medium',
      l = k === 'high' ? 'بالا' : k === 'low' ? 'پایین' : 'متوسط';
    return `<span class="priority ${c}">${l}</span>`;
  }

  function heatClass(n, m) {
    if (!n || !m) return 'heat-0';
    const r = n / m;
    return r > 0.8 ? 'heat-5' : r > 0.6 ? 'heat-4' : r > 0.4 ? 'heat-3' : r > 0.2 ? 'heat-2' : 'heat-1';
  }

  function stat(v, l, t = '') {
    return `<div class="stat">
      <strong>${v}</strong>
      <span>${l}</span>
      ${t ? `<small style="display:block;margin-top:7px;font-size:11px;font-weight:700;color:${t.color};">${t.text}</small>` : ''}
    </div>`;
  }

  function trend(c) {
    if (!c || !c.available) return c?.direction === 'new' ? { text: 'بدون سابقه برای مقایسه', color: '#f59e0b' } : null;
    const arrow = c.direction === 'up' ? '↑' : c.direction === 'down' ? '↓' : '→';
    const color = c.direction === 'up' ? '#34d399' : c.direction === 'down' ? '#fb7185' : '#cbd5e1';
    return { text: `${arrow} ${c.percentage}% نسبت به ماه قبل`, color };
  }

  function renderPriority(d) {
    const p = d.by_priority || [];
    const get = k => (p.find(x => x.key === k) || {}).count || 0;
    priorityTop.innerHTML = `
      <div class="section-title">
        <h2>🚦 گزارش اولویت‌ها</h2>
        <span class="muted">خلاصه توزیع اولویت‌ها</span>
      </div>
      <div class="priority-summary">
        <div class="priority-box high">
          <span class="name">🔴 اولویت بالا</span>
          <strong>${get('high')}</strong>
        </div>
        <div class="priority-box medium">
          <span class="name">🟠 اولویت متوسط</span>
          <strong>${get('medium')}</strong>
        </div>
        <div class="priority-box low">
          <span class="name">🟢 اولویت پایین</span>
          <strong>${get('low')}</strong>
        </div>
      </div>
    `;
  }

  function renderProductivity(d) {
    const prod = d.summary?.productivity || {};
    let card = document.getElementById('productivityCard');
    if (!card) {
      card = document.createElement('section');
      card.id = 'productivityCard';
      card.className = 'card';
      if (priorityTop) {
        priorityTop.insertAdjacentElement('afterend', card);
      }
    }
    const leadDays = prod.lead_time_days != null ? `${prod.lead_time_days} روز` : '—';
    const leadHours = prod.lead_time_hours != null ? `(${prod.lead_time_hours} ساعت)` : '';
    const onTimeRate = prod.on_time_rate != null ? `${prod.on_time_rate}٪` : '۱۰۰٪';
    const overdueRate = prod.overdue_rate != null ? `${prod.overdue_rate}٪` : '۰٪';
    const onTimeCount = prod.completed_on_time || 0;
    const lateCount = prod.completed_late || 0;
    const openOverdue = prod.open_overdue || 0;
    const openOnTrack = prod.open_on_track || 0;

    card.innerHTML = `
      <div class="section-title">
        <div>
          <h2>⚡ شاخص‌های عملکرد و بهره‌وری (Productivity Metrics)</h2>
          <span class="muted">تحلیل زمان چرخه تسک‌ها و مقایسه تحویل به‌موقع در برابر تأخیر</span>
        </div>
      </div>
      <div class="productivity-grid">
        <div class="prod-metric-box lead-time">
          <span class="p-title">⏱️ میانگین زمان تکمیل (Lead Time)</span>
          <strong class="p-value">${leadDays} <small class="muted" style="font-size:13px;font-weight:normal">${leadHours}</small></strong>
          <span class="p-sub">فاصله زمانی از ایجاد تا تکمیل نهایی وظیفه</span>
        </div>
        <div class="prod-metric-box on-time">
          <span class="p-title">🎯 نرخ انجام به‌موقع (On-Time)</span>
          <strong class="p-value" style="color:#027a48">${onTimeRate}</strong>
          <span class="p-sub">${onTimeCount} وظیفه تکمیل‌شده در مهلت مقرر</span>
        </div>
        <div class="prod-metric-box overdue-rate">
          <span class="p-title">⚠️ نرخ تحویل با تأخیر (Delayed)</span>
          <strong class="p-value" style="color:#b42318">${overdueRate}</strong>
          <span class="p-sub">${lateCount} وظیفه تکمیل‌شده پس از موعد مقرر</span>
        </div>
        <div class="prod-metric-box open-status">
          <span class="p-title">📌 وضعیت وظایف باز مهلت‌دار</span>
          <strong class="p-value" style="font-size:18px;margin-top:6px">
            <span style="color:#b42318">🔻 ${openOverdue} عقب‌افتاده</span> / 
            <span style="color:#027a48">🟢 ${openOnTrack} در مسیر</span>
          </strong>
          <span class="p-sub">کنترل پایش وظایف فعال دارای مهلت</span>
        </div>
      </div>
    `;
  }

  function pie(rows) {
    rows = rows || [];
    const total = rows.reduce((s, x) => s + Number(x.count || 0), 0);
    if (!total) return '<div class="empty">داده‌ای برای نمودار وضعیت وجود ندارد.</div>';
    const colors = ['#10b981', '#f59e0b', '#94a3b8', '#ef4444'];
    let cursor = 0;
    const parts = rows.map((x, i) => {
      const n = Number(x.count || 0), a = cursor;
      cursor += (n / total) * 360;
      return `${colors[i % colors.length]} ${a}deg ${cursor}deg`;
    }).join(',');
    return `<div style="display:grid;grid-template-columns:220px 1fr;gap:22px;align-items:center;max-width:620px">
      <div style="width:190px;height:190px;border-radius:50%;background:conic-gradient(${parts});position:relative">
        <div style="position:absolute;inset:48px;border-radius:50%;background:#fff;display:grid;place-items:center;font-weight:900">${total}</div>
      </div>
      <div>
        ${rows.map((x, i) => `
          <div style="display:flex;align-items:center;gap:8px;margin:9px 0">
            <i style="width:12px;height:12px;border-radius:4px;background:${colors[i % colors.length]}"></i>
            <span>${esc(x.label || x.status || x.category)}</span>
            <b style="margin-right:auto">${x.count}</b>
          </div>
        `).join('')}
      </div>
    </div>`;
  }

  async function getJson(url) {
    const r = await fetch(url, { cache: 'no-store' });
    let d = {};
    try {
      d = await r.json();
    } catch {}
    if (!r.ok) throw new Error(d.error === 'report_not_found' ? 'لینک گزارش معتبر نیست یا منقضی شده است.' : 'خطا در دریافت اطلاعات');
    return d;
  }

  async function downloadExport(format) {
    const r = await fetch(`/api/public-reports/monthly/${encodeURIComponent(token)}/export/${format}?${params()}`, { cache: 'no-store' });
    if (!r.ok) throw new Error('خطا در ایجاد خروجی گزارش');
    const blob = await r.blob(), url = URL.createObjectURL(blob), a = document.createElement('a');
    a.href = url;
    a.download = `task-report.${format}`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function bindFilters(options = {}) {
    const card = document.getElementById('reportFilters');
    if (!card) return;
    if (card.dataset.bound !== '1') {
      card.dataset.bound = '1';
      document.querySelectorAll('.filter-period').forEach(button =>
        button.addEventListener('click', () => {
          state.period = button.dataset.period;
          document.querySelectorAll('.filter-period').forEach(x => x.classList.toggle('active', x === button));
          document.getElementById('customDates').style.display = state.period === 'custom' ? 'grid' : 'none';
          save();
          loadSummary();
        })
      );
      document.getElementById('applyReportFilter')?.addEventListener('click', () => {
        state.search = document.getElementById('taskSearch')?.value.trim() || '';
        state.start = document.getElementById('filterStart')?.value || '';
        state.end = document.getElementById('filterEnd')?.value || '';
        state.filters.status = document.getElementById('filterStatus')?.value || '';
        state.filters.priority = document.getElementById('filterPriority')?.value || '';
        state.filters.category = document.getElementById('filterCategory')?.value || '';
        state.filters.assignee = document.getElementById('filterAssignee')?.value || '';
        state.filters.has_deadline = document.getElementById('filterHasDeadline')?.value || '';
        state.filters.overdue = document.getElementById('filterOverdue')?.value || '';
        state.filters.sort = document.getElementById('taskSort')?.value || 'newest';
        save();
        loadSummary();
        if (window.activeReportSection) loadSection(window.activeReportSection, 1);
      });
      document.getElementById('clearReportFilters')?.addEventListener('click', () => {
        state.search = '';
        state.start = '';
        state.end = '';
        state.period = 'month';
        state.filters = { status: '', priority: '', category: '', assignee: '', has_deadline: '', overdue: '', sort: 'newest' };
        save();
        loadSummary();
        if (window.activeReportSection) loadSection(window.activeReportSection, 1);
      });
      ['filterStart', 'filterEnd'].forEach(id =>
        document.getElementById(id)?.addEventListener('change', () => {
          state.start = document.getElementById('filterStart')?.value || '';
          state.end = document.getElementById('filterEnd')?.value || '';
          save();
        })
      );
      document.getElementById('exportCsv')?.addEventListener('click', () => downloadExport('csv').catch(e => alert(e.message)));
      document.getElementById('exportPdf')?.addEventListener('click', () => downloadExport('pdf').catch(e => alert(e.message)));
    }
    const mapping = {
      status: 'filterStatus',
      priority: 'filterPriority',
      category: 'filterCategory',
      assignee: 'filterAssignee',
      has_deadline: 'filterHasDeadline',
      overdue: 'filterOverdue',
      sort: 'taskSort'
    };
    Object.entries(mapping).forEach(([key, id]) => {
      const el = document.getElementById(id);
      if (el) el.value = state.filters[key] || '';
    });
  }

  function renderFiltered(section, data) {
    if (section === 'status') {
      details.innerHTML = `
        <div class="section-title">
          <h2>📌 وضعیت وظایف</h2>
          <span class="muted">بر اساس فیلتر انتخاب‌شده</span>
        </div>${pie(data.rows)}`;
      return;
    }
    if (section === 'priority') {
      details.innerHTML = `
        <div class="section-title">
          <h2>🚦 گزارش اولویت‌ها</h2>
        </div>
        <div class="priority-summary">
          ${(data.rows || []).map(x => `
            <div class="priority-box ${x.priority === 'بالا' ? 'high' : x.priority === 'پایین' ? 'low' : 'medium'}">
              <span class="name">${esc(x.priority)}</span>
              <strong>${x.count}</strong>
            </div>
          `).join('')}
        </div>`;
      return;
    }
    if (section === 'category') {
      details.innerHTML = `
        <div class="section-title">
          <h2>🗂 گزارش دسته‌بندی‌ها</h2>
        </div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>دسته‌بندی</th><th>تعداد</th></tr></thead>
            <tbody>
              ${(data.rows || []).map(x => `
                <tr>
                  <td>${esc(x.category)}</td>
                  <td><b>${x.count}</b></td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>`;
      return;
    }
    if (section === 'kanban') {
      const labels = { pending: 'شروع‌نشده', in_progress: 'در حال انجام', done: 'انجام‌شده', cancelled: 'لغوشده' };
      details.innerHTML = `
        <div class="section-title">
          <h2>🧩 کانبان</h2>
          <span class="muted">${data.total || 0} مورد</span>
        </div>
        <div class="board">
          ${Object.entries(labels).map(([k, l]) => `
            <section class="column">
              <div class="column-head">
                <h3>${l}</h3>
                <span class="count">${(data.columns?.[k] || []).length}</span>
              </div>
              ${(data.columns?.[k] || []).map(taskCard).join('') || '<div class="empty">موردی نیست</div>'}
            </section>
          `).join('')}
        </div>`;
      return;
    }
    if (section === 'week') {
      renderWeek(data);
      return;
    }
    if (section === 'habits') {
      renderHabits(data);
      return;
    }
    if (section === 'recent_changes' || section === 'activity_feed') {
      details.innerHTML = `
        <div class="section-title">
          <h2>🕘 آخرین تغییرات و فعالیت‌ها</h2>
          <span class="muted">${data.total || 0} رویداد</span>
        </div>${timeline(data.events)}`;
      return;
    }
    if (section === 'heatmap') {
      const days = data.days || [];
      const busiest = data.busiest_days || [];
      const jalaliPeriod = data.jalali_period || '';
      const dayNames = ['ش', 'ی', 'د', 'س', 'چ', 'پ', 'ج'];

      details.innerHTML = `
        <div class="section-title">
          <div>
            <h2>🗓️ تقویم فعالیت روزانه (Heatmap خورشیدی)</h2>
            <div class="muted">
              نمایش روزهای پرمشغله و نرخ انجام فعالیت‌ها بر اساس گاه‌شمار جلالی ${jalaliPeriod ? `(${esc(jalaliPeriod)})` : ''}
            </div>
          </div>
          <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
            <span class="chip">کل فعالیت‌ها: ${data.total || 0}</span>
            <span class="chip" style="background:#ecfdf3;color:#027a48">تکمیل‌شده: ${data.total_completed || 0}</span>
            <span class="chip" style="background:#eff8ff;color:#175cd3">نرخ تکمیل: ${data.overall_completion_rate || 0}٪</span>
            <span class="chip">روزهای فعال: ${data.active_days || 0} روز</span>
          </div>
        </div>

        ${busiest.length ? `
          <div class="busiest-banner">
            <strong style="display:flex;align-items:center;gap:6px">🔥 پرمشغله‌ترین روزهای دوره:</strong>
            <div class="busiest-list">
              ${busiest.map(b => `
                <span class="busy-pill">
                  <b>${esc(b.weekday_name)} ${b.jalali_day} ${esc(b.jalali_month_name)}</b>:
                  ${b.activity} فعالیت
                  <small>(${b.completed} تکمیل · ${b.created} ایجاد · نرخ: ${b.completion_rate}٪)</small>
                </span>
              `).join('')}
            </div>
          </div>
        ` : ''}

        <div class="gh-heatmap-wrapper">
          <div class="gh-heatmap-container">
            <div class="gh-day-labels">
              ${dayNames.map(name => `<span>${name}</span>`).join('')}
            </div>
            <div class="gh-cells-grid">
              ${days.map(x => `
                <div class="gh-heat-cell gh-level-${x.level || 0}"
                     title="${esc(x.weekday_name)} ${x.jalali_day} ${esc(x.jalali_month_name)} ${x.jalali_year} (${esc(x.date)})&#10;کل فعالیت: ${x.activity} مورد&#10;✅ انجام‌شده: ${x.completed} | ➕ ایجادشده: ${x.created}&#10;نرخ تکمیل: ${x.completion_rate}٪">
                </div>
              `).join('')}
            </div>
          </div>
          <div class="gh-legend">
            <span>کمتر</span>
            <i class="gh-heat-cell gh-level-0"></i>
            <i class="gh-heat-cell gh-level-1"></i>
            <i class="gh-heat-cell gh-level-2"></i>
            <i class="gh-heat-cell gh-level-3"></i>
            <i class="gh-heat-cell gh-level-4"></i>
            <span>بیشتر</span>
          </div>
        </div>
      `;
      return;
    }
    if (section === 'calendar') {
      renderCalendar(data);
      return;
    }
    renderTable(data, section === 'deadlines' ? '⏰ مهلت‌ها' : '📋 جدول وظایف');
  }

  function taskCard(x) {
    return `<article class="task-card">
      <b>${esc(x.title)}</b>
      <div class="task-meta">
        <span>${priority(x.priority)}</span>
        <span>${x.deadline ? '⏰ ' + esc(x.deadline) : 'بدون مهلت'}</span>
      </div>
      ${x.assignee ? `<div class="muted" style="margin-top:7px">👤 ${esc(x.assignee)}</div>` : ''}
    </article>`;
  }

  function timeline(events) {
    if (!events?.length) return '<div class="empty">هنوز تغییری برای نمایش وجود ندارد.</div>';
    return `<div class="timeline">
      ${events.map(x => `
        <article class="event">
          <div class="event-icon">${esc(x.icon || '•')}</div>
          <div class="event-body">
            <div class="event-head">
              <span class="event-title">${esc(x.title)}</span>
              <span class="event-time">${esc(x.created_at || '—')}</span>
            </div>
            <div class="event-task">در تسک <b>${esc(x.task_title)}</b> <span class="muted">(${esc(x.task_id)})</span></div>
            ${x.text ? `<div class="event-text">${esc(x.text)}</div>` : ''}
            <div class="event-meta">انجام‌دهنده: ${esc(x.actor || 'کاربر')}</div>
          </div>
        </article>
      `).join('')}
    </div>`;
  }

  function renderWeek(d) {
    const days = d.week?.days || [];
    details.innerHTML = `
      <div class="section-title">
        <div>
          <h2>📅 برنامه هفته</h2>
          <div class="muted">هر روز در یک بخش جداگانه و به ترتیب از امروز تا هفت روز آینده</div>
        </div>
        <span class="chip">${d.week?.total || 0} وظیفه</span>
      </div>
      <div class="week-grid">
        ${days.map((day, i) => `
          <article class="week-day ${i === 0 ? 'today' : ''}">
            <div class="day-head">
              <div class="day-title">${esc(day.label)}</div>
              <div class="day-date">${esc(day.jalali)} · ${esc(day.date)}</div>
              <span class="day-count">${day.count || 0} وظیفه</span>
            </div>
            ${day.rows?.length ? `
              <div class="table-wrap" style="border:0;border-radius:0">
                <table class="week-table">
                  <thead><tr><th class="row-no">ردیف</th><th>وظیفه</th><th>زمان</th><th>اولویت</th></tr></thead>
                  <tbody>
                    ${day.rows.map((x, j) => {
                      const raw = String(x.deadline || '');
                      const time = raw.includes('T') ? raw.split('T')[1].slice(0, 5) : (raw.length > 10 ? raw.slice(11, 16) : '—');
                      return `<tr>
                        <td class="row-no">${j + 1}</td>
                        <td>
                          <div class="week-task">${esc(x.title)}</div>
                          <div class="week-assignee">👤 ${esc(x.assignee || 'بدون مسئول')}</div>
                        </td>
                        <td>${esc(time)}</td>
                        <td>${priority(x.priority)}</td>
                      </tr>`;
                    }).join('')}
                  </tbody>
                </table>
              </div>
            ` : '<div class="empty">وظیفه‌ای برای این روز نیست.</div>'}
          </article>
        `).join('')}
      </div>`;
  }

  function renderTable(d, title) {
    const rows = d.rows || [];
    const labels = {
      newest: '↓ جدیدترین',
      oldest: '↑ قدیمی‌ترین',
      overdue: '↓ بیشترین تأخیر',
      priority: '↓ بالاترین اولویت',
      duration: '↓ طولانی‌ترین زمان انجام'
    };
    details.innerHTML = `
      <div class="section-title">
        <div>
          <h2>${title}</h2>
          <span class="muted">${d.total ?? rows.length} مورد · ${esc(labels[d.sort] || labels.newest)}</span>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th class="row-no">ردیف</th>
              <th>شناسه</th>
              <th>عنوان</th>
              <th>وضعیت</th>
              <th>اولویت</th>
              <th>مهلت</th>
              <th>دسته‌بندی</th>
              <th>مسئول</th>
            </tr>
          </thead>
          <tbody>
            ${rows.length ? rows.map((x, i) => `
              <tr>
                <td class="row-no">${((d.page || 1) - 1) * (d.page_size || 25) + i + 1}</td>
                <td>${esc(x.id)}</td>
                <td class="task-title">${esc(x.title)}</td>
                <td><span class="chip">${esc(x.status_label)}</span></td>
                <td>${priority(x.priority)}</td>
                <td>${esc(x.deadline || '—')}</td>
                <td>${esc(x.category || '—')}</td>
                <td>👤 ${esc(x.assignee || 'بدون مسئول')}</td>
              </tr>
            `).join('') : '<tr><td colspan="8" class="empty">موردی پیدا نشد.</td></tr>'}
          </tbody>
        </table>
      </div>
      ${d.pages > 1 ? `
        <div class="pager">
          ${d.page > 1 ? `<button onclick="loadSection('${d.section}',${d.page - 1})">قبلی</button>` : ''}
          <span>صفحه ${d.page} از ${d.pages}</span>
          ${d.page < d.pages ? `<button onclick="loadSection('${d.section}',${d.page + 1})">بعدی</button>` : ''}
        </div>
      ` : ''}`;
  }

  function renderHabits(d) {
    const h = d.habits || {};
    details.innerHTML = `
      <div class="section-title">
        <h2>🌱 گزارش عادت‌ها</h2>
        <span class="muted">پردازش با انتخاب کاربر</span>
      </div>
      <div class="habit-grid">
        <div class="habit-stat"><strong>${h.total_habits || 0}</strong><span>کل عادت‌ها</span></div>
        <div class="habit-stat"><strong>${h.active_habits || 0}</strong><span>عادت فعال</span></div>
        <div class="habit-stat"><strong>${h.completed_logs || 0}</strong><span>دفعات انجام</span></div>
        <div class="habit-stat"><strong>${h.completion_days || 0}</strong><span>روز فعال</span></div>
      </div>
      <div class="table-wrap" style="margin-top:14px">
        <table class="habit-table">
          <thead><tr><th class="row-no">ردیف</th><th>عادت</th><th>دسته‌بندی</th><th>تکرار</th><th>انجام‌شده</th><th>آخرین انجام</th></tr></thead>
          <tbody>
            ${(h.rows || []).map((x, i) => `
              <tr>
                <td class="row-no">${i + 1}</td>
                <td class="task-title">${esc(x.title)}</td>
                <td>${esc(x.category)}</td>
                <td>${esc(x.repeat_type)}</td>
                <td>${x.completed}</td>
                <td>${esc(x.last_done)}</td>
              </tr>
            `).join('') || '<tr><td colspan="6" class="empty">عادت فعالی ثبت نشده است.</td></tr>'}
          </tbody>
        </table>
      </div>`;
  }

  function renderCalendar(d) {
    let mode = window.calMode || 'jalali';
    const rows = d.rows || [];
    details.innerHTML = `
      <div class="section-title">
        <div>
          <h2>📅 تقویم</h2>
          <span class="muted">انتخاب نوع نمایش تاریخ</span>
        </div>
        <div class="switch">
          <button class="${mode === 'jalali' ? 'active' : ''}" onclick="window.calMode='jalali';renderCalendar(window.calendarData)">شمسی</button>
          <button class="${mode === 'gregorian' ? 'active' : ''}" onclick="window.calMode='gregorian';renderCalendar(window.calendarData)">میلادی</button>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th class="row-no">ردیف</th>
              <th>تاریخ</th>
              <th>عنوان</th>
              <th>وضعیت</th>
              <th>اولویت</th>
              <th>مسئول</th>
            </tr>
          </thead>
          <tbody>
            ${rows.map((x, i) => `
              <tr>
                <td class="row-no">${i + 1}</td>
                <td>${formatDate(x.deadline, mode)}</td>
                <td class="task-title">${esc(x.title)}</td>
                <td>${esc(x.status_label)}</td>
                <td>${priority(x.priority)}</td>
                <td>👤 ${esc(x.assignee || 'بدون مسئول')}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>`;
    window.calendarData = d;
  }

  function formatDate(v, mode) {
    if (!v) return '—';
    const m = String(v).match(/(\d{4})-(\d{1,2})-(\d{1,2})/);
    if (!m) return esc(v);
    if (mode !== 'jalali') return `${m[1]}/${String(m[2]).padStart(2, '0')}/${String(m[3]).padStart(2, '0')}`;
    return `شمسی ${+m[1] - 621}/${String(m[2]).padStart(2, '0')}/${String(m[3]).padStart(2, '0')}`;
  }

  window.loadSection = async function(section, page = 1) {
    window.activeReportSection = section;
    details.innerHTML = '<div class="loading">در حال دریافت گزارش...</div>';
    document.querySelectorAll('[data-section]').forEach(b => b.classList.toggle('active', b.dataset.section === section));
    try {
      renderFiltered(section, await getJson(filteredUrl(section, page)));
    } catch (e) {
      details.innerHTML = `<p class="error">${esc(e.message)}</p>`;
    }
  };

  window.loadSummary = async function() {
    try {
      const data = await getJson(filteredUrl()),
        s = data.summary || {},
        t = trend(s.total_change);
      const prod = s.productivity || {};

      app.innerHTML = `
        <div class="hero-top">
          <div>
            <h1>📊 گزارش تحت وب</h1>
            <p>${esc(data.period?.gregorian || '')} · ${esc(data.period?.jalali || '')}</p>
          </div>
          <div class="badge">گزارش شخصی و اختصاصی</div>
        </div>
        <div class="stats">
          ${stat(s.total || 0, 'کل وظایف', t)}
          ${stat(s.done || 0, 'انجام‌شده')}
          ${stat(s.in_progress || 0, 'در حال انجام')}
          ${stat(s.pending || 0, 'شروع‌نشده')}
          ${stat(s.cancelled || 0, 'لغوشده')}
          ${stat((s.completion_rate || 0) + '٪', 'نرخ انجام کل')}
          ${stat(s.lead_time_days != null ? s.lead_time_days + ' روز' : (s.average_completion_days != null ? s.average_completion_days + ' روز' : '—'), '⏱️ میانگین تکمیل')}
          ${stat(prod.on_time_rate != null ? prod.on_time_rate + '٪' : (s.on_time_rate != null ? s.on_time_rate + '٪' : '—'), '🎯 انجام به‌موقع')}
          ${stat(prod.overdue_rate != null ? prod.overdue_rate + '٪' : (s.overdue_rate != null ? s.overdue_rate + '٪' : '—'), '⚠️ نرخ تأخیر')}
          ${stat(s.overdue || 0, 'عقب‌افتاده باز')}
          ${stat(s.with_deadline || 0, 'دارای مهلت')}
        </div>
      `;

      if (!document.getElementById('reportFilters')) {
        priorityTop.insertAdjacentHTML('beforebegin', filterCard(data.filter_options || {}));
      }
      bindFilters(data.filter_options || {});
      renderPriority(data);
      renderProductivity(data);

      details.innerHTML = `
        <div class="section-title">
          <h2>📊 وضعیت وظایف</h2>
          <span class="muted">بر اساس فیلتر انتخاب‌شده</span>
        </div>${pie(data.by_status)}
      `;
    } catch (e) {
      app.innerHTML = `<h1>گزارش تحت وب</h1><p class="error">${esc(e.message)}</p>`;
    }
  };

  save();
  window.loadSummary();
})();