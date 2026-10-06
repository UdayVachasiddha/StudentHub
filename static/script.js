/* ==========================================================================
   StudentHub — Interaction layer
   ========================================================================== */
(() => {
  'use strict';

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const root = document.documentElement;
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------- Theme ---------- */
  $$('[data-theme-toggle]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const next = root.dataset.theme === 'light' ? 'dark' : 'light';
      root.dataset.theme = next;
      localStorage.setItem('sh-theme', next);
      const meta = $('meta[name="theme-color"]');
      if (meta) meta.content = next === 'light' ? '#f3f5fb' : '#070b16';
    });
  });

  /* ---------- Sidebar (mobile) ---------- */
  const closeSidebar = () => {
    document.body.classList.remove('sidebar-open');
    $$('[data-sidebar-toggle]').forEach((b) => b.setAttribute('aria-expanded', 'false'));
  };
  $$('[data-sidebar-toggle]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const open = document.body.classList.toggle('sidebar-open');
      btn.setAttribute('aria-expanded', String(open));
    });
  });
  $$('[data-sidebar-close]').forEach((el) => el.addEventListener('click', closeSidebar));

  /* ---------- Dropdowns ---------- */
  $$('[data-dropdown]').forEach((dd) => {
    const trigger = $('[data-dropdown-trigger]', dd);
    trigger?.addEventListener('click', (e) => {
      e.stopPropagation();
      const open = dd.classList.toggle('open');
      trigger.setAttribute('aria-expanded', String(open));
    });
  });
  document.addEventListener('click', (e) => {
    $$('[data-dropdown].open').forEach((dd) => {
      if (!dd.contains(e.target)) {
        dd.classList.remove('open');
        $('[data-dropdown-trigger]', dd)?.setAttribute('aria-expanded', 'false');
      }
    });
  });

  /* ---------- Toasts ---------- */
  const dismissToast = (toast) => {
    if (!toast || toast.classList.contains('hide')) return;
    toast.classList.add('hide');
    toast.addEventListener('animationend', () => toast.remove(), { once: true });
  };
  $$('.toast').forEach((toast, i) => {
    toast.style.setProperty('--i', i);
    $('.toast-close', toast)?.addEventListener('click', () => dismissToast(toast));
    $('.toast-bar', toast)?.addEventListener('animationend', () => dismissToast(toast));
  });

  /* ---------- Ripple ---------- */
  document.addEventListener('pointerdown', (e) => {
    const btn = e.target.closest('.btn');
    if (!btn || reduceMotion) return;
    const rect = btn.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height) * 2;
    const ink = document.createElement('span');
    ink.className = 'ripple';
    ink.style.cssText = `width:${size}px;height:${size}px;left:${e.clientX - rect.left - size / 2}px;top:${e.clientY - rect.top - size / 2}px`;
    btn.appendChild(ink);
    ink.addEventListener('animationend', () => ink.remove());
  });

  /* ---------- Spotlight hover ---------- */
  document.addEventListener('pointermove', (e) => {
    const card = e.target.closest('.spot');
    if (!card) return;
    const rect = card.getBoundingClientRect();
    card.style.setProperty('--mx', `${e.clientX - rect.left}px`);
    card.style.setProperty('--my', `${e.clientY - rect.top}px`);
  });

  /* ---------- Count-up numbers ---------- */
  const countUp = (el) => {
    const target = parseFloat(el.dataset.count) || 0;
    const decimals = parseInt(el.dataset.decimals || '0', 10);
    const suffix = el.dataset.suffix || '';
    if (reduceMotion) { el.textContent = target.toFixed(decimals) + suffix; return; }
    const duration = 1400;
    const start = performance.now();
    const step = (now) => {
      const t = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - t, 4);
      el.textContent = (target * eased).toFixed(decimals) + suffix;
      if (t < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  };

  /* ---------- Animate meters (progress / columns / rings) ---------- */
  const animateMeters = (scope) => {
    $$('[data-width]', scope).forEach((el) => { el.style.width = `${Math.min(100, parseFloat(el.dataset.width) || 0)}%`; });
    $$('[data-height]', scope).forEach((el) => { el.style.height = `${Math.max(4, Math.min(100, parseFloat(el.dataset.height) || 0))}%`; });
    $$('[data-ring]', scope).forEach((el) => { el.style.setProperty('--p', Math.min(100, parseFloat(el.dataset.ring) || 0)); });
  };

  /* ---------- Reveal on scroll ---------- */
  const revealEls = $$('.reveal');
  const onReveal = (el) => {
    el.classList.add('in');
    $$('[data-count]', el).forEach(countUp);
    if (el.matches('[data-count]')) countUp(el);
    animateMeters(el);
  };
  if ('IntersectionObserver' in window && !reduceMotion) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) { onReveal(entry.target); io.unobserve(entry.target); }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
    revealEls.forEach((el) => io.observe(el));
  } else {
    revealEls.forEach(onReveal);
  }
  // Animate anything outside a .reveal container.
  requestAnimationFrame(() => {
    $$('[data-count]').filter((el) => !el.closest('.reveal')).forEach(countUp);
    $$('[data-width],[data-height],[data-ring]').filter((el) => !el.closest('.reveal')).forEach((el) => animateMeters(el.parentElement));
  });

  /* ---------- Relative time ---------- */
  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' });
  const ago = (date) => {
    const diff = (date - new Date()) / 1000;
    const units = [['year', 31536000], ['month', 2592000], ['week', 604800], ['day', 86400], ['hour', 3600], ['minute', 60]];
    for (const [unit, secs] of units) {
      if (Math.abs(diff) >= secs) return rtf.format(Math.round(diff / secs), unit);
    }
    return 'just now';
  };
  $$('time[data-ago]').forEach((el) => {
    const d = new Date(el.getAttribute('datetime'));
    if (isNaN(d)) return;
    el.title = el.textContent.trim();
    el.textContent = ago(d);
  });

  /* ---------- Password visibility & strength ---------- */
  $$('[data-toggle-password]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const input = btn.parentElement.querySelector('input');
      const show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      btn.classList.toggle('showing', show);
      btn.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
      input.focus();
    });
  });

  $$('[data-strength]').forEach((meter) => {
    const input = document.getElementById(meter.dataset.strength);
    const label = $('.strength-label', meter);
    const names = ['Use at least 8 characters', 'Weak', 'Fair', 'Good', 'Strong'];
    input?.addEventListener('input', () => {
      const v = input.value;
      let score = 0;
      if (v.length >= 8) score++;
      if (/[A-Z]/.test(v) && /[a-z]/.test(v)) score++;
      if (/\d/.test(v)) score++;
      if (/[^A-Za-z0-9]/.test(v) || v.length >= 14) score++;
      if (v.length < 8) score = v.length ? 1 : 0;
      meter.dataset.level = String(score);
      label.textContent = v.length ? names[score] : names[0];
    });
  });

  $$('[data-match]').forEach((input) => {
    const other = document.getElementById(input.dataset.match);
    const field = input.closest('.field');
    const hint = $('.match-hint', field);
    const check = () => {
      if (!input.value) { delete field.dataset.state; hint.textContent = ''; input.setCustomValidity(''); return; }
      const ok = input.value === other.value;
      field.dataset.state = ok ? 'ok' : 'bad';
      hint.textContent = ok ? '✓ Passwords match' : 'Passwords do not match';
      input.setCustomValidity(ok ? '' : 'Passwords do not match');
    };
    input.addEventListener('input', check);
    other?.addEventListener('input', check);
  });

  /* ---------- Fill demo credentials ---------- */
  $$('[data-fill]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const [user, pass] = btn.dataset.fill.split(':');
      const u = $('#username');
      const p = $('#password');
      if (u && p) { u.value = user; p.value = pass; p.focus(); }
    });
  });

  /* ---------- Confirm modal ---------- */
  const modal = $('#confirm-modal');
  let pendingForm = null;
  const closeModal = () => { modal?.classList.remove('open'); pendingForm = null; };
  $$('form[data-confirm]').forEach((form) => {
    form.addEventListener('submit', (e) => {
      if (form.dataset.confirmed === 'yes' || !modal) return;
      e.preventDefault();
      pendingForm = form;
      $('#confirm-title', modal).textContent = form.dataset.confirmTitle || 'Are you sure?';
      $('#confirm-text', modal).textContent = form.dataset.confirm;
      modal.classList.add('open');
      setTimeout(() => $('[data-modal-confirm]', modal)?.focus(), 50);
    });
  });
  modal?.addEventListener('click', (e) => { if (e.target === modal || e.target.closest('[data-modal-cancel]')) closeModal(); });
  $('[data-modal-confirm]', modal || document)?.addEventListener('click', () => {
    if (!pendingForm) return;
    pendingForm.dataset.confirmed = 'yes';
    pendingForm.requestSubmit ? pendingForm.requestSubmit() : pendingForm.submit();
    closeModal();
  });

  /* ---------- Loading state on submit ---------- */
  document.addEventListener('submit', (e) => {
    const form = e.target;
    if (e.defaultPrevented || form.method.toLowerCase() !== 'post') return;
    const btn = e.submitter || $('button[type="submit"], button:not([type])', form);
    if (btn && btn.classList.contains('btn')) setTimeout(() => btn.classList.add('loading'), 0);
  });

  /* ---------- Dropzone ---------- */
  $$('.dropzone').forEach((zone) => {
    const input = $('input[type="file"]', zone);
    const title = $('.dz-title', zone);
    const hint = $('.dz-hint', zone);
    const original = { title: title.textContent, hint: hint.textContent };
    const update = () => {
      const file = input.files && input.files[0];
      zone.classList.toggle('has-file', !!file);
      title.textContent = file ? file.name : original.title;
      hint.textContent = file ? `${(file.size / 1024 / 1024).toFixed(2)} MB · ready to upload` : original.hint;
    };
    ['dragenter', 'dragover'].forEach((ev) => zone.addEventListener(ev, () => zone.classList.add('drag')));
    ['dragleave', 'drop'].forEach((ev) => zone.addEventListener(ev, () => zone.classList.remove('drag')));
    input.addEventListener('change', update);
  });

  /* ---------- Tabs ---------- */
  $$('[data-tabs]').forEach((tabs) => {
    const buttons = $$('[role="tab"]', tabs);
    const indicator = $('.tab-indicator', tabs);
    const move = (btn) => {
      if (!indicator) return;
      indicator.style.width = `${btn.offsetWidth}px`;
      indicator.style.transform = `translateX(${btn.offsetLeft}px)`;
    };
    const select = (btn, focus) => {
      buttons.forEach((b) => {
        const on = b === btn;
        b.setAttribute('aria-selected', String(on));
        b.tabIndex = on ? 0 : -1;
        const panel = document.getElementById(b.getAttribute('aria-controls'));
        if (panel) {
          panel.hidden = !on;
          if (on) animateMeters(panel);
        }
      });
      move(btn);
      if (focus) btn.focus();
      history.replaceState(null, '', `#${btn.dataset.tab}`);
    };
    buttons.forEach((btn, i) => {
      btn.addEventListener('click', () => select(btn));
      btn.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowRight') select(buttons[(i + 1) % buttons.length], true);
        if (e.key === 'ArrowLeft') select(buttons[(i - 1 + buttons.length) % buttons.length], true);
      });
    });
    const initial = buttons.find((b) => `#${b.dataset.tab}` === location.hash) || buttons[0];
    if (initial) requestAnimationFrame(() => select(initial));
    window.addEventListener('resize', () => {
      const active = buttons.find((b) => b.getAttribute('aria-selected') === 'true');
      if (active) move(active);
    });
  });

  /* ---------- Auto-submit filters ---------- */
  $$('[data-autosubmit]').forEach((form) => {
    $$('select, input[type="date"]', form).forEach((el) => el.addEventListener('change', () => form.requestSubmit ? form.requestSubmit() : form.submit()));
  });

  /* ---------- Roster: live filter, view toggle, sort ---------- */
  const roster = $('[data-roster]');
  if (roster) {
    const items = $$('[data-search]', roster);
    const searchInput = $('[data-live-search]');
    const counter = $('[data-visible-count]');
    const empty = $('[data-live-empty]', roster);

    const applyFilter = () => {
      const q = (searchInput?.value || '').trim().toLowerCase();
      let visible = 0;
      items.forEach((item) => {
        const show = !q || item.dataset.search.includes(q);
        item.hidden = !show;
        if (show && item.matches('tr')) visible++;
      });
      if (!items.some((i) => i.matches('tr'))) visible = items.filter((i) => !i.hidden).length;
      if (counter) counter.textContent = visible;
      if (empty) empty.hidden = visible !== 0 || items.length === 0;
    };
    searchInput?.addEventListener('input', applyFilter);

    const viewBtns = $$('[data-view-btn]');
    const setView = (view) => {
      roster.dataset.view = view;
      viewBtns.forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.viewBtn === view)));
      localStorage.setItem('sh-roster-view', view);
      $$('.reveal:not(.in)', roster).forEach(onReveal);
    };
    viewBtns.forEach((b) => b.addEventListener('click', () => setView(b.dataset.viewBtn)));
    setView(localStorage.getItem('sh-roster-view') || 'table');
  }

  $$('table[data-sortable]').forEach((table) => {
    const tbody = $('tbody', table);
    $$('th[data-sort]', table).forEach((th, _, all) => {
      th.addEventListener('click', () => {
        const idx = Array.from(th.parentElement.children).indexOf(th);
        const dir = th.classList.contains('asc') ? 'desc' : 'asc';
        all.forEach((h) => h.classList.remove('asc', 'desc'));
        th.classList.add(dir);
        const rows = $$('tr', tbody).filter((r) => r.children.length > 1);
        rows.sort((a, b) => {
          const av = (a.children[idx].dataset.value ?? a.children[idx].textContent).trim().toLowerCase();
          const bv = (b.children[idx].dataset.value ?? b.children[idx].textContent).trim().toLowerCase();
          return (dir === 'asc' ? 1 : -1) * av.localeCompare(bv, undefined, { numeric: true });
        });
        rows.forEach((r) => tbody.appendChild(r));
      });
    });
  });

  /* ---------- Attendance register ---------- */
  const register = $('[data-register]');
  if (register) {
    const saveBar = $('.save-bar', register);
    const counts = { Present: $('[data-att="Present"]'), Late: $('[data-att="Late"]'), Absent: $('[data-att="Absent"]') };
    const ring = $('[data-att-ring]');
    const ringLabel = $('[data-att-rate]');
    const rows = $$('tr[data-status]', register);

    const tally = () => {
      const totals = { Present: 0, Late: 0, Absent: 0 };
      rows.forEach((row) => {
        const checked = $('input:checked', row);
        if (checked) { totals[checked.value]++; row.dataset.status = checked.value; }
      });
      Object.entries(counts).forEach(([k, el]) => {
        if (!el) return;
        if (el.textContent !== String(totals[k])) {
          el.textContent = totals[k];
          el.classList.add('bump');
          setTimeout(() => el.classList.remove('bump'), 220);
        }
      });
      const total = rows.length || 1;
      const rate = Math.round(((totals.Present + totals.Late) / total) * 100);
      if (ring) ring.style.setProperty('--p', rows.length ? rate : 0);
      if (ringLabel) ringLabel.textContent = `${rows.length ? rate : 0}%`;
    };

    register.addEventListener('change', (e) => {
      if (e.target.matches('input[type="radio"]')) { tally(); saveBar?.classList.add('dirty'); }
    });
    $$('[data-mark-all]').forEach((btn) => {
      btn.addEventListener('click', () => {
        rows.forEach((row) => {
          const input = $(`input[value="${btn.dataset.markAll}"]`, row);
          if (input) input.checked = true;
        });
        tally();
        saveBar?.classList.add('dirty');
      });
    });
    register.addEventListener('submit', () => saveBar?.classList.remove('dirty'));
    window.addEventListener('beforeunload', (e) => {
      if (saveBar?.classList.contains('dirty')) { e.preventDefault(); e.returnValue = ''; }
    });
    tally();
  }

  $$('[data-date-shift]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const input = document.getElementById(btn.dataset.target);
      const d = input.value ? new Date(`${input.value}T00:00:00`) : new Date();
      if (btn.dataset.dateShift === 'today') {
        const now = new Date();
        d.setFullYear(now.getFullYear(), now.getMonth(), now.getDate());
      } else {
        d.setDate(d.getDate() + parseInt(btn.dataset.dateShift, 10));
      }
      const pad = (n) => String(n).padStart(2, '0');
      input.value = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
      input.form.requestSubmit ? input.form.requestSubmit() : input.form.submit();
    });
  });

  /* ---------- Assessment live preview ---------- */
  const scoreInput = $('#score');
  const maxInput = $('#max_score');
  const preview = $('[data-score-preview]');
  if (scoreInput && maxInput && preview) {
    const update = () => {
      const s = parseFloat(scoreInput.value);
      const m = parseFloat(maxInput.value);
      if (isNaN(s) || isNaN(m) || m <= 0) { preview.textContent = '—'; preview.style.color = ''; return; }
      const pct = Math.round((s / m) * 100);
      preview.textContent = `${pct}%`;
      preview.style.color = pct >= 75 ? 'var(--success)' : pct >= 50 ? 'var(--warning)' : 'var(--danger)';
    };
    scoreInput.addEventListener('input', update);
    maxInput.addEventListener('input', update);
  }

  /* ---------- Copy to clipboard ---------- */
  $$('[data-copy]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(btn.dataset.copy);
        const old = btn.getAttribute('data-tip');
        btn.setAttribute('data-tip', 'Copied!');
        setTimeout(() => btn.setAttribute('data-tip', old || 'Copy'), 1400);
      } catch (_) { /* clipboard unavailable */ }
    });
  });

  /* ---------- Avatar initials preview (student form) ---------- */
  const nameInput = $('[data-avatar-source]');
  const avatarPreview = $('[data-avatar-preview]');
  const namePreview = $('[data-name-preview]');
  if (nameInput && avatarPreview) {
    const update = () => {
      const v = nameInput.value.trim();
      const initials = v.split(/\s+/).slice(0, 2).map((w) => w[0] || '').join('').toUpperCase() || 'ST';
      let hue = 0;
      for (const ch of v) hue += ch.charCodeAt(0);
      avatarPreview.textContent = initials;
      avatarPreview.style.setProperty('--h', (hue * 37) % 360);
      if (namePreview) namePreview.textContent = v || 'New student';
    };
    nameInput.addEventListener('input', update);
  }

  /* ---------- Keyboard shortcuts ---------- */
  document.addEventListener('keydown', (e) => {
    const typing = /INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName);
    if ((e.key === '/' && !typing) || ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k')) {
      const search = $('#global-search');
      if (search) { e.preventDefault(); search.focus(); search.select(); }
    }
    if (e.key === 'Escape') {
      closeSidebar();
      closeModal();
      $$('[data-dropdown].open').forEach((dd) => dd.classList.remove('open'));
      if (typing) document.activeElement.blur();
    }
  });
})();
