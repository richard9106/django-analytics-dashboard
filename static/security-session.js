(() => {
  const config = document.currentScript;
  if (!config || window.nuviaSecuritySession) return;
  window.nuviaSecuritySession = true;
  const pending = config.dataset.pending === 'true';
  const idle = Number(config.dataset.idleSeconds) * 1000;
  const deadline = Date.now() + Number(config.dataset.deadlineSeconds) * 1000;
  let activeAt = Date.now(), dirty = false, exiting = false;
  const channel = typeof BroadcastChannel === 'function' ? new BroadcastChannel('nuvia-session') : null;
  const token = () => {
    const cookie = document.cookie.split('; ').find(v => v.startsWith('csrftoken='));
    return cookie ? decodeURIComponent(cookie.slice(10)) : document.querySelector('[name=csrfmiddlewaretoken]')?.value;
  };
  const login = () => window.location.assign('/login/?session_expired=1');
  const signOut = async () => {
    if (exiting) return;
    exiting = true;
    channel?.postMessage({type: 'logout'});
    const csrf = token() || '';
    document.body.replaceChildren();
    try { await fetch('/logout/', {method: 'POST', credentials: 'same-origin', signal: AbortSignal.timeout(3000), headers: {'X-CSRFToken': csrf}}); }
    catch (_) { /* Hide protected content even when logout cannot reach the server. */ }
    finally { login(); }
  };
  const expired = () => Date.now() >= deadline || (!pending && Date.now() - activeAt >= idle);
  const activity = event => {
    if (!event.isTrusted || exiting || expired()) return;
    activeAt = Date.now(); dirty = true;
    channel?.postMessage({type: 'activity', at: activeAt});
  };
  for (const name of ['pointerdown', 'keydown', 'scroll', 'touchstart']) {
    document.addEventListener(name, activity, {passive: true});
  }
  if (channel) channel.onmessage = ({data}) => {
    if (data.type === 'logout') { exiting = true; login(); }
    if (data.type === 'activity' && !expired() && Number.isFinite(data.at)) {
      activeAt = Math.min(Date.now(), Math.max(activeAt, data.at)); dirty = true;
    }
  };
  const check = () => { if (!exiting && expired()) signOut(); };
  document.addEventListener('visibilitychange', check);
  setInterval(check, 1000);
  if (!pending) setInterval(async () => {
    if (exiting || !dirty || expired()) return;
    dirty = false;
    try {
      const response = await fetch('/accounts/security/session/', {method: 'POST', credentials: 'same-origin', headers: {'X-CSRFToken': token() || ''}});
      if (response.status === 401 || response.redirected) { exiting = true; login(); }
    } catch (_) { /* The local expiry timer still closes the page when offline. */ }
  }, 60000);
})();
