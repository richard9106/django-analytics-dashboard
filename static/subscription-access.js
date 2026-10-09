// The server enforces read-only access; this explains unavailable actions before a click.
(() => {
  const explanation = 'Read-only mode: restore the practice subscription to make changes.';
  const safePosts = ['/logout/', '/accounts/profile/', '/accounts/export/', '/accounts/security/',
    '/billing/subscribe/', '/billing/stripe/customer-portal/', '/billing/stripe/change-plan/',
    '/billing/stripe/plan-preview/', '/help/contact/'];
  const explain = (element) => {
    element.setAttribute('aria-disabled', 'true');
    element.setAttribute('title', explanation);
    element.classList.add('subscription-disabled');
  };
  document.querySelectorAll('a[href]').forEach((link) => {
    const path = new URL(link.href, window.location.href).pathname;
    if (/\/(new|create|edit|delete|assign)\//.test(path) ||
        /\/integrations\/google\/(connect|callback)\//.test(path) ||
        /\/payments\/stripe\/connect\//.test(path)) {
      explain(link);
      link.addEventListener('click', (event) => { event.preventDefault(); event.stopPropagation(); });
    }
  });
  document.querySelectorAll('form').forEach((form) => {
    if (form.method.toLowerCase() !== 'post') return;
    const path = new URL(form.action, window.location.href).pathname;
    if (safePosts.some((allowed) => path.startsWith(allowed))) return;
    form.querySelectorAll('button, input:not([type="hidden"]), select, textarea').forEach((control) => {
      control.disabled = true;
      explain(control);
    });
    form.addEventListener('submit', (event) => event.preventDefault());
  });
})();
