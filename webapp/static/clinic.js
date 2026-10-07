(() => {
  const tg = window.Telegram?.WebApp;
  if (tg) { tg.ready(); tg.expand(); }

  const pageParams = new URLSearchParams(location.search);
  const botKey = pageParams.get('bot_key') || 'clinic';
  const initData = tg?.initData || '';
  const headers = {
    'Content-Type': 'application/json',
    ...(initData ? {'X-Telegram-Init-Data': initData} : {})
  };

  const $ = id => document.getElementById(id);
  const state = {
    scopes: [],
    workspaces: [],
    orgId: '',
    branches: [],
    patients: [],
    patientsTotal: 0,
    patientOffset: 0,
    patientLimit: 25,
    sessions: [],
    currentPatient: null,
    currentPatientPayload: null,
    editingSession: null
  };

  const els = {
    workspace: $('workspace-select'), role: $('role-badge'),
    title: $('page-title'), subtitle: $('page-subtitle'),
    primary: $('primary-action'), refresh: $('refresh-btn'),
    flash: $('flash'), patientsView: $('patients-view'), sessionsView: $('sessions-view'),
    patientDetail: $('patient-detail-view'), patientsBody: $('patients-body'),
    patientsEmpty: $('patients-empty'), patientsCount: $('patients-count'),
    patientsPage: $('patients-page'), patientsPrev: $('patients-prev'), patientsNext: $('patients-next'),
    patientSearch: $('patient-search'), patientBranchFilter: $('patient-branch-filter'),
    sessionsBody: $('sessions-body'), sessionsEmpty: $('sessions-empty'),
    sessionsCount: $('sessions-count'), sessionSearch: $('session-search'),
    sessionStatusFilter: $('session-status-filter'), sessionBranchFilter: $('session-branch-filter')
  };

  const statusLabels = {
    active:'فعال', inactive:'غیرفعال', scheduled:'برنامه‌ریزی‌شده',
    completed:'تکمیل‌شده', cancelled:'لغوشده', no_show:'عدم حضور',
    rescheduled:'تغییر زمان', pending:'در انتظار'
  };

  function esc(value) {
    return String(value ?? '').replace(/[&<>"']/g, ch => ({
      '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'
    }[ch]));
  }

  function apiUrl(path, query={}) {
    const url = new URL(path, location.origin);
    if (botKey) url.searchParams.set('bot_key', botKey);
    if (state.orgId && path.startsWith('/api/clinic/') && path !== '/api/clinic/scopes') {
      url.searchParams.set('organization_id', state.orgId);
    }
    Object.entries(query).forEach(([key,value]) => {
      if (value !== undefined && value !== null && String(value) !== '') {
        url.searchParams.set(key, String(value));
      }
    });
    return url.pathname + url.search;
  }

  async function request(path, {method='GET', query={}, body}={}) {
    const response = await fetch(apiUrl(path, query), {
      method, headers, cache:'no-store',
      ...(body !== undefined ? {body:JSON.stringify(body)} : {})
    });
    let payload = {};
    try { payload = await response.json(); } catch (_) {}
    if (!response.ok) {
      const error = new Error(payload.error || ('HTTP ' + response.status));
      error.status = response.status;
      throw error;
    }
    return payload;
  }

  function notify(message, kind='success') {
    els.flash.textContent = message;
    els.flash.className = 'flash ' + kind;
    els.flash.hidden = false;
    clearTimeout(notify.timer);
    notify.timer = setTimeout(() => { els.flash.hidden = true; }, 3500);
  }

  function formatDate(value, withTime=true) {
    if (!value) return '—';
    const date = new Date(String(value).replace(' ', 'T'));
    if (Number.isNaN(date.getTime())) return esc(value);
    try {
      return new Intl.DateTimeFormat('fa-IR-u-ca-persian', {
        year:'numeric', month:'2-digit', day:'2-digit',
        ...(withTime ? {hour:'2-digit', minute:'2-digit'} : {})
      }).format(date);
    } catch (_) {
      return date.toLocaleString();
    }
  }

  function toLocalInput(value) {
    if (!value) return '';
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return String(value).slice(0,16);
    const local = new Date(d.getTime() - d.getTimezoneOffset()*60000);
    return local.toISOString().slice(0,16);
  }

  function statusPill(status) {
    const key = String(status || '');
    return '<span class="status ' + esc(key) + '">' + esc(statusLabels[key] || key || '—') + '</span>';
  }

  function currentRoute() {
    const parts = location.pathname.split('/').filter(Boolean);
    if (parts[0] !== 'clinic') return {name:'patients'};
    if (parts[1] === 'sessions') return {name:'sessions'};
    if (parts[1] === 'patients' && parts[2]) return {name:'patient', id:parts[2]};
    return {name:'patients'};
  }

  function routePath(path) {
    const url = new URL(path, location.origin);
    if (botKey) url.searchParams.set('bot_key', botKey);
    history.pushState({}, '', url.pathname + url.search);
    renderRoute();
  }

  function setNav(active) {
    document.querySelectorAll('.nav-item').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.route === active);
    });
  }

  function showOnly(target) {
    [els.patientsView, els.sessionsView, els.patientDetail].forEach(el => el.hidden = el !== target);
  }

  async function renderRoute() {
    const route = currentRoute();
    if (route.name === 'sessions') {
      setNav('sessions');
      showOnly(els.sessionsView);
      els.title.textContent = 'جلسات';
      els.subtitle.textContent = 'برنامه‌ریزی و مدیریت جلسات بیماران';
      els.primary.textContent = '+ جلسه جدید';
      await loadSessions();
      return;
    }
    if (route.name === 'patient') {
      setNav('patients');
      showOnly(els.patientDetail);
      els.title.textContent = 'پرونده بیمار';
      els.subtitle.textContent = 'مشخصات، راه‌های تماس و جلسات بیمار';
      els.primary.textContent = '+ جلسه جدید';
      await loadPatient(route.id);
      return;
    }
    setNav('patients');
    showOnly(els.patientsView);
    els.title.textContent = 'بیماران';
    els.subtitle.textContent = 'مدیریت پرونده بیماران و اطلاعات تماس';
    els.primary.textContent = '+ بیمار جدید';
    await loadPatients();
  }

  function branchOptions(select, includeAll=true) {
    const current = select.value;
    const options = [];
    if (includeAll) options.push('<option value="">همه شعب</option>');
    for (const b of state.branches) {
      options.push('<option value="' + esc(b.id) + '">' + esc(b.name || b.id) + '</option>');
    }
    select.innerHTML = options.join('');
    if ([...select.options].some(o => o.value === current)) select.value = current;
  }

  async function loadScopes() {
    const data = await request('/api/clinic/scopes');
    state.scopes = Array.isArray(data.items) ? data.items : [];
    const byId = new Map();
    state.scopes.forEach(s => {
      if (!byId.has(s.organization_id)) byId.set(s.organization_id, {id:s.organization_id, name:s.name});
    });
    state.workspaces = [...byId.values()];
    if (!state.workspaces.length) throw new Error('clinic_workspace_required');
    const requested = pageParams.get('organization_id');
    state.orgId = state.workspaces.some(w => w.id === requested) ? requested : state.workspaces[0].id;
    els.workspace.innerHTML = state.workspaces.map(w =>
      '<option value="' + esc(w.id) + '">' + esc(w.name || w.id) + '</option>'
    ).join('');
    els.workspace.value = state.orgId;
    const scope = state.scopes.find(s => s.organization_id === state.orgId);
    els.role.textContent = scope?.role || 'member';
    $('workspace-title').textContent = scope?.name || 'فضای کار کلینیک';
  }

  async function loadBranches() {
    try {
      const data = await request('/api/clinic/branches');
      state.branches = Array.isArray(data.items) ? data.items : [];
    } catch (error) {
      const unique = new Set(state.scopes.filter(s => s.organization_id === state.orgId).map(s => s.branch_id).filter(Boolean));
      state.branches = [...unique].map(id => ({id, name:id}));
    }
    [els.patientBranchFilter, els.sessionBranchFilter].forEach(s => branchOptions(s, true));
    branchOptions($('patient-branch'), false);
  }

  function patientTyped(row) {
    if (row?.typed && typeof row.typed === 'object') return row.typed;
    try { return JSON.parse(row?.data_json || '{}'); } catch (_) { return {}; }
  }

  function patientStatus(row) {
    return patientTyped(row).status || row.status || 'active';
  }

  function renderPatients() {
    els.patientsCount.textContent = state.patientsTotal.toLocaleString('fa-IR') + ' بیمار';
    els.patientsEmpty.hidden = state.patients.length > 0;
    els.patientsBody.innerHTML = state.patients.map(p => {
      const typed = patientTyped(p);
      const code = typed.patient_id || p.reference_id || '—';
      return '<tr>' +
        '<td><button class="patient-link" data-open-patient="' + esc(p.id) + '">' + esc(p.title || 'بدون نام') + '</button>' +
          '<div class="subtle">' + esc([typed.first_name, typed.last_name].filter(Boolean).join(' ')) + '</div></td>' +
        '<td>' + esc(code) + '</td>' +
        '<td>' + esc(p.primary_phone || '—') + '</td>' +
        '<td>' + statusPill(patientStatus(p)) + '</td>' +
        '<td>' + formatDate(p.created_at, false) + '</td>' +
        '<td><div class="row-actions">' +
          '<button class="text-btn" data-open-patient="' + esc(p.id) + '" type="button">مشاهده</button>' +
          '<button class="text-btn" data-edit-patient="' + esc(p.id) + '" type="button">ویرایش</button>' +
        '</div></td></tr>';
    }).join('');
    const page = Math.floor(state.patientOffset/state.patientLimit)+1;
    const pages = Math.max(1, Math.ceil(state.patientsTotal/state.patientLimit));
    els.patientsPage.textContent = 'صفحه ' + page.toLocaleString('fa-IR') + ' از ' + pages.toLocaleString('fa-IR');
    els.patientsPrev.disabled = state.patientOffset <= 0;
    els.patientsNext.disabled = state.patientOffset + state.patientLimit >= state.patientsTotal;
  }

  async function loadPatients() {
    els.patientsBody.innerHTML = '<tr class="loading-row"><td colspan="6">در حال دریافت بیماران…</td></tr>';
    const data = await request('/api/clinic/typed/patients', {query:{
      search:els.patientSearch.value.trim(),
      branch_id:els.patientBranchFilter.value,
      limit:state.patientLimit,
      offset:state.patientOffset
    }});
    state.patients = data.items || [];
    state.patientsTotal = Number(data.total || 0);
    renderPatients();
  }

  function sessionTyped(row) { return row?.typed && typeof row.typed === 'object' ? row.typed : {}; }

  function renderSessions() {
    els.sessionsCount.textContent = state.sessions.length.toLocaleString('fa-IR') + ' جلسه در این صفحه';
    els.sessionsEmpty.hidden = state.sessions.length > 0;
    els.sessionsBody.innerHTML = state.sessions.map(s => {
      const typed = sessionTyped(s);
      const when = typed.scheduled_at || s.deadline;
      return '<tr>' +
        '<td><button class="patient-link" data-open-patient="' + esc(s.parent_task_id) + '">' + esc(s.patient_name || '—') + '</button></td>' +
        '<td>' + esc(s.title || 'جلسه') + '</td>' +
        '<td>' + formatDate(when) + '</td>' +
        '<td>' + esc(typed.session_type || '—') + '</td>' +
        '<td>' + statusPill(typed.status || s.status) + '</td>' +
        '<td><button class="text-btn" data-edit-session="' + esc(s.id) + '" type="button">ویرایش</button></td>' +
      '</tr>';
    }).join('');
  }

  async function loadSessions() {
    els.sessionsBody.innerHTML = '<tr class="loading-row"><td colspan="6">در حال دریافت جلسات…</td></tr>';
    const data = await request('/api/clinic/typed/sessions', {query:{
      search:els.sessionSearch.value.trim(),
      branch_id:els.sessionBranchFilter.value,
      status:els.sessionStatusFilter.value,
      limit:100
    }});
    state.sessions = data.items || [];
    renderSessions();
  }

  function infoCard(label, value) {
    return '<div class="info-card"><small>' + esc(label) + '</small><strong>' + esc(value || '—') + '</strong></div>';
  }

  function renderPatientDetail(payload) {
    const item = payload.item || {};
    const typed = item.typed || {};
    state.currentPatient = item;
    state.currentPatientPayload = payload;
    $('patient-name').textContent = item.title || 'بدون نام';
    $('patient-avatar').textContent = (item.title || 'ب').trim().slice(0,1);
    $('patient-meta').textContent = 'کد بیمار: ' + (typed.patient_id || item.reference_id || '—') + ' · ' + (statusLabels[typed.status] || typed.status || 'فعال');
    $('profile-grid').innerHTML = [
      infoCard('نام', typed.first_name),
      infoCard('نام خانوادگی', typed.last_name),
      infoCard('کد بیمار', typed.patient_id || item.reference_id),
      infoCard('تاریخ تولد', typed.date_of_birth ? formatDate(typed.date_of_birth, false) : '—'),
      infoCard('وضعیت', statusLabels[typed.status] || typed.status || 'فعال'),
      infoCard('شعبه', branchName(item.unit_id))
    ].join('');
    renderContacts(payload.contact_points || []);
    const sessions = (payload.children?.items || []).filter(x => x.work_item_type === 'session');
    renderPatientSessions(sessions);
    $('clinical-grid').innerHTML = [
      infoCard('سابقه بیماری', typed.disease_history),
      infoCard('بیماری‌های زمینه‌ای', typed.chronic_conditions),
      infoCard('حساسیت‌ها', typed.allergies),
      infoCard('داروها', typed.medications),
      infoCard('تشخیص‌ها', typed.diagnoses),
      infoCard('یادداشت بالینی', typed.clinical_notes)
    ].join('');
  }

  function renderContacts(items) {
    const active = items.filter(x => x.status !== 'inactive');
    $('contact-list').innerHTML = active.length ? active.map(c =>
      '<div class="stack-item"><div class="stack-main"><strong>' + esc(c.value || '—') +
      (c.is_primary ? ' <span class="status active">اصلی</span>' : '') +
      '</strong><small>' + esc((c.type || 'contact') + (c.label ? ' · ' + c.label : '')) + '</small></div>' +
      '<div class="stack-actions"><button class="text-btn" data-edit-contact="' + esc(c.id) + '" type="button">ویرایش</button>' +
      '<button class="text-btn" data-remove-contact="' + esc(c.id) + '" type="button">حذف</button></div></div>'
    ).join('') : '<div class="empty-state"><p>راه تماسی ثبت نشده است.</p></div>';
  }

  function renderPatientSessions(items) {
    $('patient-sessions-list').innerHTML = items.length ? items.map(s => {
      const typed = s.typed || {};
      return '<div class="stack-item"><div class="stack-main"><strong>' + esc(s.title || 'جلسه') + '</strong>' +
        '<small>' + formatDate(typed.scheduled_at || s.deadline) + ' · ' + esc(typed.session_type || 'بدون نوع') + '</small></div>' +
        statusPill(typed.status || s.status) +
        '<div class="stack-actions"><button class="text-btn" data-edit-session="' + esc(s.id) + '" type="button">ویرایش</button></div></div>';
    }).join('') : '<div class="empty-state"><p>برای این بیمار جلسه‌ای ثبت نشده است.</p></div>';
  }

  async function loadPatient(id) {
    const payload = await request('/api/clinic/typed/items/' + encodeURIComponent(id));
    renderPatientDetail(payload);
  }

  function branchName(id) {
    return state.branches.find(b => String(b.id) === String(id))?.name || id || '—';
  }

  function openModal(id) { $(id).hidden = false; }
  function closeModal(id) { $(id).hidden = true; }

  function openPatientModal(item=null) {
    const typed = item?.typed || {};
    $('patient-id').value = item?.id || '';
    $('patient-display-name').value = item?.title || '';
    $('patient-first-name').value = typed.first_name || '';
    $('patient-last-name').value = typed.last_name || '';
    $('patient-reference').value = typed.patient_id || item?.reference_id || '';
    $('patient-dob').value = typed.date_of_birth || '';
    $('patient-status').value = typed.status || 'active';
    $('patient-modal-title').textContent = item ? 'ویرایش بیمار' : 'بیمار جدید';
    $('patient-form-error').hidden = true;
    $('patient-phone').value = '';
    $('new-patient-phone-field').hidden = Boolean(item);
    const branch = item?.unit_id || els.patientBranchFilter.value || state.branches[0]?.id || '';
    $('patient-branch').value = branch;
    $('patient-branch').disabled = Boolean(item);
    openModal('patient-modal');
  }

  async function editPatient(id) {
    if (state.currentPatient?.id === id) return openPatientModal(state.currentPatient);
    const payload = await request('/api/clinic/typed/items/' + encodeURIComponent(id));
    openPatientModal(payload.item);
  }

  async function savePatient(event) {
    event.preventDefault();
    const id = $('patient-id').value;
    const fields = {
      patient_id:$('patient-reference').value.trim() || null,
      first_name:$('patient-first-name').value.trim() || null,
      last_name:$('patient-last-name').value.trim() || null,
      date_of_birth:$('patient-dob').value || null,
      status:$('patient-status').value
    };
    try {
      if (id) {
        await request('/api/clinic/typed/items/' + encodeURIComponent(id), {
          method:'PATCH', body:{title:$('patient-display-name').value.trim(), fields}
        });
        notify('اطلاعات بیمار به‌روزرسانی شد.');
        closeModal('patient-modal');
        if (currentRoute().name === 'patient') await loadPatient(id); else await loadPatients();
        return;
      }
      const branchId = $('patient-branch').value;
      if (!branchId) throw new Error('branch_required');
      const created = await request('/api/clinic/typed/patients', {method:'POST', body:{
        display_name:$('patient-display-name').value.trim(),
        reference_id:$('patient-reference').value.trim() || null,
        branch_id:branchId
      }});
      const newId = created.item.id;
      await request('/api/clinic/typed/items/' + encodeURIComponent(newId), {method:'PATCH', body:{fields}});
      const phone = $('patient-phone').value.trim();
      if (phone) {
        await request('/api/clinic/typed/contact-points', {method:'POST', body:{
          task_id:newId, type:'phone', label:'mobile', value:phone, is_primary:true
        }});
      }
      notify('بیمار جدید ایجاد شد.');
      closeModal('patient-modal');
      state.patientOffset = 0;
      routePath('/clinic/patients');
    } catch (error) {
      $('patient-form-error').hidden = false;
      $('patient-form-error').textContent = error.message === 'branch_required' ? 'انتخاب شعبه الزامی است.' : 'ذخیره بیمار انجام نشد.';
    }
  }

  function findContact(id) {
    return (state.currentPatientPayload?.contact_points || []).find(c => String(c.id) === String(id));
  }

  function openContactModal(contact=null) {
    $('contact-id').value = contact?.id || '';
    $('contact-type').value = contact?.type || 'phone';
    $('contact-type').disabled = Boolean(contact);
    $('contact-label').value = contact?.label || '';
    $('contact-value').value = contact?.value || '';
    $('contact-primary').checked = Boolean(contact?.is_primary);
    $('contact-modal-title').textContent = contact ? 'ویرایش راه تماس' : 'افزودن راه تماس';
    $('contact-form-error').hidden = true;
    openModal('contact-modal');
  }

  async function saveContact(event) {
    event.preventDefault();
    const id = $('contact-id').value;
    const payload = {
      value:$('contact-value').value.trim(),
      label:$('contact-label').value.trim(),
      is_primary:$('contact-primary').checked,
      status:'active'
    };
    try {
      if (id) {
        await request('/api/clinic/typed/contact-points/' + encodeURIComponent(id), {method:'PATCH', body:payload});
      } else {
        await request('/api/clinic/typed/contact-points', {method:'POST', body:{
          task_id:state.currentPatient.id,
          type:$('contact-type').value,
          ...payload
        }});
      }
      closeModal('contact-modal');
      notify('راه تماس ذخیره شد.');
      await loadPatient(state.currentPatient.id);
    } catch (_) {
      $('contact-form-error').hidden = false;
      $('contact-form-error').textContent = 'ذخیره راه تماس انجام نشد.';
    }
  }

  async function removeContact(id) {
    if (!confirm('این راه تماس غیرفعال شود؟')) return;
    await request('/api/clinic/typed/contact-points/' + encodeURIComponent(id), {method:'PATCH', body:{status:'inactive'}});
    notify('راه تماس حذف شد.');
    await loadPatient(state.currentPatient.id);
  }

  async function ensurePatientChoices(selected='') {
    if (!state.patients.length) {
      const data = await request('/api/clinic/typed/patients', {query:{limit:100,offset:0}});
      state.patients = data.items || [];
    }
    $('session-patient').innerHTML = state.patients.map(p =>
      '<option value="' + esc(p.id) + '">' + esc(p.title || p.id) + '</option>'
    ).join('');
    if (selected) $('session-patient').value = selected;
  }

  async function openSessionModal(session=null, patientId='') {
    state.editingSession = session;
    const typed = session?.typed || {};
    const parentId = session?.parent_task_id || patientId || state.currentPatient?.id || '';
    await ensurePatientChoices(parentId);
    $('session-id').value = session?.id || '';
    $('session-patient').disabled = Boolean(session);
    $('session-title').value = session?.title || '';
    $('session-at').value = toLocalInput(typed.scheduled_at || session?.deadline);
    $('session-type').value = typed.session_type || '';
    $('session-status').value = typed.status || session?.status || 'scheduled';
    $('session-modal-title').textContent = session ? 'ویرایش جلسه' : 'جلسه جدید';
    $('session-form-error').hidden = true;
    openModal('session-modal');
  }

  function findSession(id) {
    const global = state.sessions.find(s => String(s.id) === String(id));
    if (global) return global;
    return (state.currentPatientPayload?.children?.items || []).find(s => String(s.id) === String(id));
  }

  async function saveSession(event) {
    event.preventDefault();
    const id = $('session-id').value;
    const localAt = $('session-at').value;
    const scheduledAt = localAt ? new Date(localAt).toISOString() : '';
    const selectedStatus = $('session-status').value;
    const sessionType = $('session-type').value.trim();
    try {
      if (!id) {
        await request('/api/clinic/typed/children', {method:'POST', body:{
          parent_task_id:$('session-patient').value,
          item_type:'session',
          title:$('session-title').value.trim(),
          scheduled_at:scheduledAt,
          fields:{session_type:sessionType || null, status:selectedStatus}
        }});
      } else {
        const previous = state.editingSession || findSession(id) || {};
        const previousTyped = previous.typed || {};
        await request('/api/clinic/typed/items/' + encodeURIComponent(id), {
          method:'PATCH', body:{title:$('session-title').value.trim(), fields:{session_type:sessionType || null}}
        });
        const oldAt = previousTyped.scheduled_at || previous.deadline || '';
        if (scheduledAt && new Date(oldAt).getTime() !== new Date(scheduledAt).getTime()) {
          await request('/api/clinic/typed/sessions/' + encodeURIComponent(id) + '/reschedule', {
            method:'POST', body:{scheduled_at:scheduledAt}
          });
        }
        const oldStatus = previousTyped.status || previous.status || 'scheduled';
        if (selectedStatus !== oldStatus) {
          await request('/api/clinic/typed/items/' + encodeURIComponent(id) + '/status', {
            method:'PATCH', body:{status:selectedStatus}
          });
        }
      }
      closeModal('session-modal');
      notify(id ? 'جلسه به‌روزرسانی شد.' : 'جلسه جدید ثبت شد.');
      const route = currentRoute();
      if (route.name === 'patient') await loadPatient(route.id); else await loadSessions();
    } catch (_) {
      $('session-form-error').hidden = false;
      $('session-form-error').textContent = 'ذخیره جلسه انجام نشد. تاریخ، بیمار و سطح دسترسی را بررسی کنید.';
    }
  }

  function switchDetailTab(name) {
    document.querySelectorAll('.detail-tab').forEach(tab => tab.classList.toggle('active', tab.dataset.detailTab === name));
    ['profile','contact','sessions','clinical'].forEach(key => {
      $('detail-' + key).hidden = key !== name;
    });
  }

  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('clinic-theme', theme);
    $('theme-toggle').textContent = theme === 'dark' ? '☀' : '☾';
  }

  function debounce(fn, wait=250) {
    let timer;
    return (...args) => { clearTimeout(timer); timer=setTimeout(() => fn(...args), wait); };
  }

  async function refreshCurrent() {
    const route = currentRoute();
    if (route.name === 'patient') return loadPatient(route.id);
    if (route.name === 'sessions') return loadSessions();
    return loadPatients();
  }

  document.querySelectorAll('.nav-item').forEach(btn => btn.addEventListener('click', () => routePath('/clinic/' + btn.dataset.route)));
  document.querySelectorAll('[data-close-modal]').forEach(btn => btn.addEventListener('click', () => closeModal(btn.dataset.closeModal)));
  document.querySelectorAll('.modal-backdrop').forEach(backdrop => backdrop.addEventListener('click', e => { if (e.target === backdrop) closeModal(backdrop.id); }));
  document.querySelectorAll('.detail-tab').forEach(tab => tab.addEventListener('click', () => switchDetailTab(tab.dataset.detailTab)));

  els.primary.addEventListener('click', async () => {
    const route = currentRoute();
    if (route.name === 'patients') openPatientModal();
    else if (route.name === 'patient') await openSessionModal(null, route.id);
    else await openSessionModal();
  });
  els.refresh.addEventListener('click', refreshCurrent);
  $('patient-back').addEventListener('click', () => routePath('/clinic/patients'));
  $('patient-edit').addEventListener('click', () => openPatientModal(state.currentPatient));
  $('add-contact').addEventListener('click', () => openContactModal());
  $('add-patient-session').addEventListener('click', () => openSessionModal(null, state.currentPatient?.id || ''));
  $('patient-form').addEventListener('submit', savePatient);
  $('contact-form').addEventListener('submit', saveContact);
  $('session-form').addEventListener('submit', saveSession);

  document.addEventListener('click', async e => {
    const patientButton = e.target.closest('[data-open-patient]');
    if (patientButton) return routePath('/clinic/patients/' + encodeURIComponent(patientButton.dataset.openPatient));
    const editPatientButton = e.target.closest('[data-edit-patient]');
    if (editPatientButton) return editPatient(editPatientButton.dataset.editPatient);
    const editContactButton = e.target.closest('[data-edit-contact]');
    if (editContactButton) return openContactModal(findContact(editContactButton.dataset.editContact));
    const removeContactButton = e.target.closest('[data-remove-contact]');
    if (removeContactButton) return removeContact(removeContactButton.dataset.removeContact);
    const editSessionButton = e.target.closest('[data-edit-session]');
    if (editSessionButton) return openSessionModal(findSession(editSessionButton.dataset.editSession));
  });

  els.patientSearch.addEventListener('input', debounce(() => { state.patientOffset=0; loadPatients(); }));
  els.patientBranchFilter.addEventListener('change', () => { state.patientOffset=0; loadPatients(); });
  els.sessionSearch.addEventListener('input', debounce(loadSessions));
  els.sessionStatusFilter.addEventListener('change', loadSessions);
  els.sessionBranchFilter.addEventListener('change', loadSessions);
  els.patientsPrev.addEventListener('click', () => { state.patientOffset=Math.max(0,state.patientOffset-state.patientLimit); loadPatients(); });
  els.patientsNext.addEventListener('click', () => { state.patientOffset+=state.patientLimit; loadPatients(); });
  els.workspace.addEventListener('change', async () => {
    state.orgId=els.workspace.value;
    state.patients=[]; state.sessions=[]; state.patientOffset=0;
    const scope=state.scopes.find(s=>s.organization_id===state.orgId);
    els.role.textContent=scope?.role||'member';
    $('workspace-title').textContent=scope?.name||'فضای کار کلینیک';
    await loadBranches();
    await renderRoute();
  });
  $('theme-toggle').addEventListener('click', () => applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'));
  window.addEventListener('popstate', renderRoute);

  async function start() {
    applyTheme(localStorage.getItem('clinic-theme') || (tg?.colorScheme === 'dark' ? 'dark' : 'light'));
    const allowed = window.WebAppAuthGuard ? await window.WebAppAuthGuard.ready : true;
    if (!allowed) return;
    try {
      await loadScopes();
      await loadBranches();
      await renderRoute();
    } catch (error) {
      console.error('clinic_workspace_start_failed', error);
      notify(error.message === 'clinic_workspace_required' ? 'برای این حساب فضای کاری کلینیک تعریف نشده است.' : 'بارگذاری فضای کار کلینیک انجام نشد.', 'error');
    }
  }
  start();
})();
