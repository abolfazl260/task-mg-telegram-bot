(() => {
  const tg = window.Telegram?.WebApp; if (tg) { tg.ready(); tg.expand(); }
  const params=new URLSearchParams(location.search);
  const pathParts=location.pathname.split('/').filter(Boolean);
  const id=params.get('id') || window.__dashboardTaskId || (pathParts[0]==='task' ? pathParts[2] : '');
  const botKey=params.get('bot_key')||'';
  const titleEl=document.getElementById('task-title'), taskEl=document.getElementById('task'), stateEl=document.getElementById('state'), editBtn=document.getElementById('edit'), form=document.getElementById('edit-form');
  const headers={ 'Content-Type':'application/json', ...(tg?.initData?{'X-Telegram-Init-Data':tg.initData}:{}) };
  const apiUrl=p=>`${p}?bot_key=${encodeURIComponent(botKey)}`;
  const text=v=>String(v??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#039;'}[c]));
  const labels={pending:'در انتظار',in_progress:'در حال انجام',done:'انجام شده',cancelled:'لغو شده',low:'پایین',medium:'متوسط',high:'بالا'};
  const field=(label,value)=>value!==undefined&&value!==null&&String(value)!==''?`<div class="task-detail-row"><strong>${text(label)}</strong><span>${text(value)}</span></div>`:'';
  const date=v=>v?text(v):'—';
  document.getElementById('back').addEventListener('click',()=>location.href=`/tasks/${encodeURIComponent(window.__dashboardTaskToken||botKey)}`);
  let current;
  function fillForm(t){document.getElementById('edit-title').value=t.title||'';document.getElementById('edit-description').value=t.description||'';document.getElementById('edit-status').value=t.status||'pending';document.getElementById('edit-priority').value=t.priority||'medium';document.getElementById('edit-deadline').value=(t.deadline||'').replace(' ','T').slice(0,16);document.getElementById('edit-category').value=t.category||'';document.getElementById('edit-tags').value=t.tags||'';}
  function renderComments(comments){
    if(!Array.isArray(comments)||!comments.length) return '<section class="task-section"><h3>💬 کامنت‌ها</h3><p class="muted">هنوز کامنتی ثبت نشده است.</p></section>';
    return `<section class="task-section"><h3>💬 کامنت‌ها (${comments.length})</h3>${comments.map(c=>{const body=c.text||c.caption||c.file_name||c.emoji||c.content||'بدون متن';const type=c.type&&c.type!=='text'?` · ${text(c.type)}`:'';return `<div class="history-item"><div><strong>${text(c.author_name||'کاربر')}</strong>${c.author_username?` <span class="muted">@${text(c.author_username)}</span>`:''}${type}</div><div class="muted">${date(c.created_at)}</div><div class="history-content">${text(body)}</div></div>`;}).join('')}</section>`;
  }
  function renderHistory(history){
    if(!Array.isArray(history)||!history.length) return '<section class="task-section"><h3>📜 تاریخچه</h3><p class="muted">تاریخچه‌ای برای این تسک ثبت نشده است.</p></section>';
    return `<section class="task-section"><h3>📜 تاریخچه تخصیص</h3>${history.map(h=>`<div class="history-item"><div><strong>${text(h.action||'تغییر')}</strong></div><div>${text(h.old_assignee_name||'بدون مسئول')} ← ${text(h.new_assignee_name||'بدون مسئول')}</div><div class="muted">${date(h.created_at)} · انجام‌دهنده: ${text(h.actor_id||'—')}</div></div>`).join('')}</section>`;
  }
  function render(t){
    current=t;titleEl.textContent=t.title||'وظیفه';
    const status=labels[t.status]||t.status||'—', priority=labels[t.priority]||t.priority||'—';
    taskEl.innerHTML=`<h2 class="task-title">${text(t.title||'بدون عنوان')}</h2><section class="task-section"><h3>📋 اطلاعات تسک</h3>${field('شناسه',t.id)}${field('وضعیت',status)}${field('اولویت',priority)}${field('مهلت',t.deadline)}${field('دسته‌بندی',t.category)}${field('تگ‌ها',t.tags)}${field('توضیحات',t.description)}${field('ایجاد شده در',t.created_at)}${field('تکمیل شده در',t.completed_at)}${field('شناسه تیم',t.team_id)}${field('مسئول',t.assignee_name)}${field('نام کاربری مسئول',t.assignee_username)}${field('شناسه مسئول',t.assignee_id)}${field('شناسه ایجادکننده',t.user_id)}${field('بات',t.bot_key)}</section>${renderComments(t.comments)}${renderHistory(t.assignment_history)}`;
    taskEl.hidden=false;editBtn.hidden=false;stateEl.hidden=true;fillForm(t);
  }
  async function load(){
    if(!id||!botKey){stateEl.textContent='اطلاعات لازم مشخص نشده است.';return;}
    try{const r=await fetch(apiUrl(`/api/tasks/${encodeURIComponent(id)}`),{headers});if(!r.ok)throw Error(r.status);const data=await r.json();if(!data.task)throw Error('task_not_found');render(data.task);}catch(e){stateEl.textContent='دریافت جزئیات وظیفه انجام نشد.';console.error(e);}
  }
  editBtn.addEventListener('click',()=>{form.hidden=false;editBtn.hidden=true;});
  form.addEventListener('submit',async e=>{e.preventDefault();stateEl.hidden=false;stateEl.textContent='در حال ذخیره تغییرات...';const payload={title:document.getElementById('edit-title').value.trim(),description:document.getElementById('edit-description').value,priority:document.getElementById('edit-priority').value,deadline:document.getElementById('edit-deadline').value,category:document.getElementById('edit-category').value,tags:document.getElementById('edit-tags').value};try{let r=await fetch(apiUrl(`/api/tasks/${encodeURIComponent(id)}`),{method:'PATCH',headers,body:JSON.stringify(payload)});if(!r.ok)throw Error(r.status);render((await r.json()).task);form.hidden=true;editBtn.hidden=false;stateEl.hidden=true;}catch(e){stateEl.textContent='ذخیره تغییرات انجام نشد.';console.error(e);}});
  load();
})();
