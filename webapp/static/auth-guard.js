(() => {
  const protectedRoot = document.querySelector('[data-auth-protected]');
  const tg = window.Telegram?.WebApp;
  const path = window.location.pathname;
  const publicTokenRoute = /^\/tasks\/[^/]+\/?$/.test(path) || /^\/task\/[^/]+\/[^/]+\/?$/.test(path);
  const nativeFetch = window.fetch.bind(window);
  const params = new URLSearchParams(window.location.search);
  const botKey = params.get('bot_key') || '';

  let activeModal = null;
  let state = 'checking';

  function hideProtectedContent() {
    if (protectedRoot) protectedRoot.hidden = true;
  }

  function revealProtectedContent() {
    if (protectedRoot) protectedRoot.hidden = false;
  }

  function closeModal() {
    activeModal?.remove();
    activeModal = null;
  }

  function renderModal({ title, message, kind = 'auth' }) {
    hideProtectedContent();
    closeModal();

    const backdrop = document.createElement('div');
    backdrop.dataset.authModal = kind;
    backdrop.setAttribute('role', 'presentation');
    backdrop.style.cssText = [
      'position:fixed',
      'inset:0',
      'z-index:99999',
      'display:flex',
      'align-items:center',
      'justify-content:center',
      'padding:20px',
      'background:rgba(15,23,42,.55)',
      'backdrop-filter:blur(4px)'
    ].join(';');

    const dialog = document.createElement('section');
    dialog.setAttribute('role', 'dialog');
    dialog.setAttribute('aria-modal', 'true');
    dialog.setAttribute('aria-labelledby', 'webapp-auth-title');
    dialog.style.cssText = [
      'width:min(430px,100%)',
      'background:var(--bg-primary,#fff)',
      'color:var(--text-primary,#111827)',
      'border:1px solid var(--border-light,#e5e7eb)',
      'border-radius:16px',
      'box-shadow:0 24px 80px rgba(15,23,42,.25)',
      'padding:24px',
      'text-align:right',
      'font-family:inherit'
    ].join(';');

    const heading = document.createElement('h2');
    heading.id = 'webapp-auth-title';
    heading.textContent = title;
    heading.style.cssText = 'margin:0 0 10px;font-size:20px';

    const text = document.createElement('p');
    text.textContent = message;
    text.style.cssText = 'margin:0;line-height:1.9;color:var(--text-secondary,#4b5563);font-size:14px';

    const actions = document.createElement('div');
    actions.style.cssText = 'display:flex;justify-content:flex-end;gap:10px;margin-top:20px';

    const closeButton = document.createElement('button');
    closeButton.type = 'button';
    closeButton.textContent = tg?.close ? 'بستن' : 'بازگشت';
    closeButton.style.cssText = [
      'border:0',
      'border-radius:10px',
      'padding:10px 16px',
      'cursor:pointer',
      'font:inherit',
      'font-weight:700',
      'background:var(--button-color,#2481cc)',
      'color:var(--button-text-color,#fff)'
    ].join(';');
    closeButton.addEventListener('click', () => {
      if (tg?.close) {
        tg.close();
      } else if (window.history.length > 1) {
        window.history.back();
      }
    });

    actions.appendChild(closeButton);
    dialog.append(heading, text, actions);
    backdrop.appendChild(dialog);
    document.body.appendChild(backdrop);
    activeModal = backdrop;
  }

  function showAuthRequired() {
    state = 'unauthenticated';
    renderModal({
      kind: 'authentication-required',
      title: 'احراز هویت لازم است',
      message: 'برای استفاده از این بخش باید از طریق تلگرام احراز هویت شوید. لطفاً این صفحه را از داخل ربات تلگرام باز کنید.'
    });
  }

  function showAccessDenied() {
    state = 'forbidden';
    renderModal({
      kind: 'access-denied',
      title: 'دسترسی مجاز نیست',
      message: 'حساب شما احراز هویت شده است، اما مجوز دسترسی به این بخش را ندارد.'
    });
  }

  function showAuthCheckFailed() {
    state = 'error';
    renderModal({
      kind: 'auth-check-failed',
      title: 'بررسی احراز هویت انجام نشد',
      message: 'در بررسی وضعیت ورود مشکلی رخ داد. اتصال خود را بررسی کنید و دوباره از داخل تلگرام وارد شوید.'
    });
  }

  function shouldHandleApiResponse(input) {
    const raw = typeof input === 'string' ? input : input?.url;
    if (!raw) return false;
    try {
      const url = new URL(raw, window.location.href);
      return (
        url.origin === window.location.origin &&
        url.pathname.startsWith('/api/') &&
        !url.pathname.startsWith('/api/public-tasks/')
      );
    } catch (_) {
      return false;
    }
  }

  window.fetch = async (input, init) => {
    const response = await nativeFetch(input, init);
    if (shouldHandleApiResponse(input)) {
      if (response.status === 401) {
        showAuthRequired();
      } else if (response.status === 403) {
        showAccessDenied();
      }
    }
    return response;
  };

  async function checkAuthentication() {
    if (!protectedRoot) {
      state = 'not-applicable';
      return true;
    }

    if (publicTokenRoute) {
      state = 'public-token';
      revealProtectedContent();
      return true;
    }

    hideProtectedContent();

    if (!tg?.initData) {
      showAuthRequired();
      return false;
    }

    try {
      const query = botKey ? `?bot_key=${encodeURIComponent(botKey)}` : '';
      const response = await nativeFetch(`/api/me${query}`, {
        headers: { 'X-Telegram-Init-Data': tg.initData },
        cache: 'no-store'
      });

      if (response.status === 401) {
        showAuthRequired();
        return false;
      }
      if (response.status === 403) {
        showAccessDenied();
        return false;
      }
      if (!response.ok) {
        showAuthCheckFailed();
        return false;
      }

      state = 'authenticated';
      closeModal();
      revealProtectedContent();
      return true;
    } catch (error) {
      console.error('webapp_auth_check_failed', error);
      showAuthCheckFailed();
      return false;
    }
  }

  const ready = checkAuthentication();
  window.WebAppAuthGuard = {
    ready,
    get state() { return state; },
    showAuthRequired,
    showAccessDenied
  };
})();