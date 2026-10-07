// Sign-up and forgot-password flows, shared by teachers.ycltesthk.com and students.ycltesthk.com.
// The server decides the realm from the hostname and enforces every limit; this file only drives the
// steps and shows the resend countdown the server hands back (60 s ×3, then 15 min, 60 min, 24 h).
const R = {
  $: (id) => document.getElementById(id),
  async post(path, body) {
    let r, j = {};
    try {
      r = await fetch('/api/reg/' + path, {method: 'POST', credentials: 'same-origin',
        headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body || {})});
      try { j = await r.json(); } catch (e) { j = {}; }
    } catch (e) { return {ok: false, error: '連線錯誤，請檢查網絡後再試。', http: 0}; }
    j.http = r.status;
    if (!j.ok && !j.error) j.error = '系統繁忙，請稍後再試。';
    return j;
  },
  show(step) { document.querySelectorAll('[data-step]').forEach((e) => { e.hidden = e.dataset.step !== step; }); },
  msg(id, text, good) { const e = R.$(id); if (!e) return; e.textContent = text || ''; e.classList.toggle('good', !!good); },
  busy(btn, on, text) {
    const b = R.$(btn); if (!b) return;
    if (on) { b.dataset.idle = b.dataset.idle || b.textContent; b.textContent = text || '處理中…'; b.disabled = true; }
    else { b.textContent = b.dataset.idle || b.textContent; b.disabled = false; }
  },
  fmt(s) {
    if (s >= 3600) { const h = Math.floor(s / 3600), m = Math.ceil((s % 3600) / 60); return h + ' 小時' + (m ? ' ' + m + ' 分' : ''); }
    if (s >= 60) return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0');
    return s + ' 秒';
  },
  _timers: {},
  countdown(btnId, secs) {
    const b = R.$(btnId); if (!b) return;
    clearInterval(R._timers[btnId]);
    const label = b.dataset.label || (b.dataset.label = b.textContent);
    const end = Date.now() + (secs || 0) * 1000;
    const tick = () => {
      const s = Math.ceil((end - Date.now()) / 1000);
      if (s <= 0) { b.disabled = false; b.textContent = label; clearInterval(R._timers[btnId]); return; }
      b.disabled = true; b.textContent = label + '（' + R.fmt(s) + '）';
    };
    tick(); R._timers[btnId] = setInterval(tick, 1000);
  },
  val(id) { const e = R.$(id); return e ? e.value.trim() : ''; },

  register(realm) {
    let token = null;
    R.$('f').addEventListener('submit', async (e) => {
      e.preventDefault(); R.msg('err', '');
      if (R.$('password').value !== R.$('password2').value) return R.msg('err', '兩次輸入的密碼不一致。');
      const body = {name: R.val('name'), email: R.val('email'), username: R.val('username'), password: R.$('password').value};
      if (realm === 'teacher') { body.school = R.val('school'); body.phone = R.val('phone'); }
      else body.joincode = R.val('joincode');
      R.busy('go', true, '提交中…'); const j = await R.post('register', body); R.busy('go', false);
      if (!j.ok) return R.msg('err', j.error);
      token = j.token; R.$('sentto').textContent = j.email;
      R.show('code'); R.countdown('resend', j.resend_after); R.$('code').focus();
    });
    R.$('cf').addEventListener('submit', async (e) => {
      e.preventDefault(); R.msg('cerr', '');
      R.busy('verify', true, '驗證中…'); const j = await R.post('register/verify', {token, code: R.val('code')}); R.busy('verify', false);
      if (!j.ok) { R.msg('cerr', j.error); if (j.http === 410) R.$('code').value = ''; return; }
      R.show(j.status === 'active' ? 'done' : 'approval');
    });
    R.$('resend').addEventListener('click', async () => {
      R.msg('cerr', ''); const j = await R.post('register/resend', {token});
      if (j.ok) { R.msg('cerr', '新的驗證碼已寄出。', true); R.countdown('resend', j.resend_after); }
      else { R.msg('cerr', j.error); if (j.retry_after) R.countdown('resend', j.retry_after); }
    });
  },

  forgot() {
    let token = null, session = null;
    const start = async () => {
      R.msg('ierr', '');
      R.busy('send', true, '寄出中…'); const j = await R.post('forgot', {id: R.val('ident')}); R.busy('send', false);
      if (!j.ok) { R.msg('ierr', j.error); if (j.retry_after) R.countdown('send', j.retry_after); return; }
      token = j.token; R.show('code'); R.countdown('resend', j.resend_after); R.$('code').focus();
    };
    R.$('fi').addEventListener('submit', (e) => { e.preventDefault(); start(); });
    R.$('resend').addEventListener('click', async () => {
      R.msg('cerr', ''); const j = await R.post('forgot/resend', {token});
      if (j.ok) { R.msg('cerr', '如帳號存在，新的驗證碼已寄出。', true); R.countdown('resend', j.resend_after); }
      else { R.msg('cerr', j.error); if (j.retry_after) R.countdown('resend', j.retry_after); if (j.http === 410) R.show('id'); }
    });
    R.$('cf').addEventListener('submit', async (e) => {
      e.preventDefault(); R.msg('cerr', '');
      R.busy('verify', true, '驗證中…'); const j = await R.post('forgot/verify', {token, code: R.val('code')}); R.busy('verify', false);
      if (!j.ok) { R.msg('cerr', j.error); return; }
      session = j.session;
      const list = R.$('accounts'); list.innerHTML = '';
      (j.accounts || []).forEach((a, i) => {
        const id = 'acc' + i, row = document.createElement('label'); row.className = 'acct';
        const r = document.createElement('input'); r.type = 'radio'; r.name = 'acct'; r.value = a.u; r.id = id;
        if (j.accounts.length === 1) r.checked = true;
        const t = document.createElement('span'); t.textContent = a.u + (a.name ? '（' + a.name + '）' : '');
        row.append(r, t); list.append(row);
      });
      R.$('acctnote').hidden = (j.accounts || []).length < 2;
      R.show('pw'); R.$('password').focus();
    });
    R.$('pf').addEventListener('submit', async (e) => {
      e.preventDefault(); R.msg('perr', '');
      const pick = document.querySelector('input[name=acct]:checked');
      if (!pick) return R.msg('perr', '請選擇要重設的帳號。');
      if (R.$('password').value !== R.$('password2').value) return R.msg('perr', '兩次輸入的密碼不一致。');
      R.busy('save', true, '儲存中…');
      const j = await R.post('forgot/reset', {session, username: pick.value, password: R.$('password').value});
      R.busy('save', false);
      if (!j.ok) { R.msg('perr', j.error); if (j.http === 410) R.show('id'); return; }
      R.$('doneuser').textContent = pick.value; R.show('done');
    });
  },
};
