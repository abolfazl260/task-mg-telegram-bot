(() => {
  const tg = window.Telegram?.WebApp; if (tg) { tg.ready(); tg.expand(); }
  const params=new URLSearchParams(location.search), id=params.get('id'), botKey=params.get('bot_key')||'';
  const titleEl=document.getElementById('task-title'), taskEl=document.getElementById('task'), stateEl=document.getElementById('state'), editBtn=document.getElementById('edit'), form=document.getElementById('edit-form');
  const headers={ 'Content-Type':'application/json', ...(tg?.initData?{'X-Telegram-Init-Data':tg.initData}:{}) };
  const apiUrl=p=>`${p}?bot_key=${encodeURIComponent(botKey)}`;
  const text=v=>String(v??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#039;'}[c]));
  const labels={pending:'در انتظار',in_progress:'در حال انجام',done:'انجام شده',cancelled:'لغو شده',low:'پایین',medium:'متوسط',high:'بالا'};
  document.getElementById('back').addEventListener('click',()=>location.href=`/?bot_key=${encodeURIComponent(botKey)}`);
  let current;
  function fillForm(t){document.getElementById('edit-title').value=t.title||'';document.getElementById('edit-description').value=t.description||'';document.getElementById('edit-status').value=t.status||'pending';document.getElementById('edit-priority').value=t.priority||'medium';document.getElementById('edit-deadline').value=(t.deadline||'').replace(' ','T').slice(0,16);document.getElementById('edit-category').value=t.category||'';document.getElementById('edit-tags').value=t.tags||'';}
  function render(t){current=t;titleEl.textContent=t.title||'وظیفه';taskEl.innerHTML=`<h2 class="task-title">${text(t.title||'بدون عنوان')}</h2>${t.description?`<p>${text(t.description)}</p>`:''}<div class="task-meta"><span class="badge">وضعیت: ${text(labels[t.status]||t.status||'')}</span><span class="badge">اولویت: ${text(labels[t.priority]||t.priority||'')}</span>${t.deadline?`<span>مهلت: ${text(t.deadline)}</span>`:''}${t.category?`<span>دسته: ${text(t.category)}</span>`:''}${t.tags?`<span>تگ: ${text(t.tags)}</span>`:''}</div>`;taskEl.hidden=false;editBtn.hidden=false;stateEl.hidden=true;fillForm(t);}
  async function load(){if(!id||!botKey){stateEl.textContent='اطلاعات لازم مشخص نشده است.';return;}try{const r=await fetch(apiUrl(`/api/tasks/${encodeURIComponent(id)}`),{headers});if(!r.ok)throw Error(r.status);render((await r.json()).task);}catch(e){stateEl.textContent='دریافت جزئیات وظیفه انجام نشد.';console.error(e);}}
  editBtn.addEventListener('click',()=>{form.hidden=false;editBtn.hidden=true;});
  form.addEventListener('submit',async e=>{e.preventDefault();stateEl.hidden=false;stateEl.textContent='در حال ذخیره تغییرات...';const payload={title:document.getElementById('edit-title').value.trim(),description:document.getElementById('edit-description').value,priority:document.getElementById('edit-priority').value,deadline:document.getElementById('edit-deadline').value,category:document.getElementById('edit-category').value,tags:document.getElementById('edit-tags').value};try{let r=await fetch(apiUrl(`/api/tasks/${encodeURIComponent(id)}`),{method:'PATCH',headers,body:JSON.stringify(payload)});if(!r.ok)throw Error(r.status);render((await r.json()).task);form.hidden=true;editBtn.hidden=false;stateEl.hidden=true;}catch(e){stateEl.textContent='ذخیره تغییرات انجام نشد.';console.error(e);}});
  load();
})();
