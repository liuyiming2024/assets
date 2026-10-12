/* 人物档案与日记 —— 三层架构
 *
 *   原始随手记 → 改写（最大程度尊重原文）→ 第1层 大日记
 *             → 提炼 + 分门别类归到人 → 第2层 小日记
 *             → 总体概括 → 第3层 个人档案（含相册）
 *
 * ⚠ 三条硬规矩：
 *   1. 显示任何内容之前先鉴权。没权限就什么都别渲染 ——
 *      "先渲染再隐藏"是障眼法，数据其实已经到客户端了。
 *   2. 原文永不被覆盖。改写写进 polished 列，body 保持原样。
 *   3. 整理结果永远新增一版，不覆盖 —— 整理错了能退回。
 */
(function (g) {
  'use strict';
  var el = document.getElementById('app');
  var state = { people: [], cur: null, tab: 'write' };  /* cur=null 表示"不归属任何人" */

  function h(tag, cls, txt) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (txt !== undefined) e.textContent = txt;
    return e;
  }
  function toast(msg, kind) {
    var t = h('div', 'card ' + (kind || ''), msg);
    t.style.cssText = 'position:fixed;top:12px;right:12px;max-width:300px;z-index:99';
    document.body.appendChild(t);
    setTimeout(function () { t.remove(); }, 4000);
  }
  function rpc(n, a) {
    return g.SB.rpc(n, a).catch(function (e) {
      var m = e && e.message ? e.message : '';
      /* 统一账号体系里的权限拒绝，文案要用人话 */
      if (/权限|没有权限|denied/i.test(m)) throw new Error('没有权限');
      throw e;
    });
  }

  /* ---------- 登录 ---------- */
  function renderLogin() {
    el.innerHTML = '';
    var c = h('div', 'card');
    c.appendChild(h('h1', null, '人物档案与日记'));
    c.appendChild(h('p', 'muted', '需要站长账号才能进入。账号走统一账号体系。'));
    var nick = h('input'); nick.placeholder = '昵称';
    var pwd = h('input'); pwd.type = 'password'; pwd.placeholder = '密码';
    var btn = h('button', 'primary', '登录');
    var row = h('div', 'row');
    row.appendChild(nick); row.appendChild(pwd); row.appendChild(btn);
    c.appendChild(row);
    btn.onclick = function () {
      btn.disabled = true;
      g.SB.login(nick.value, pwd.value).then(boot).catch(function (e) {
        toast('登录失败：' + (e.message || '网络错误'), 'err');
        btn.disabled = false;
      });
    };
    el.appendChild(c);
  }

  /* ---------- 启动：先鉴权，再渲染 ---------- */
  function boot() {
    if (!g.SB.hasToken()) { renderLogin(); return; }
    /* ⚠ 先问能不能看。拿不到就是没权限，一个字都不渲染。 */
    rpc('profile_list').then(function (r) {
      state.people = r || [];
      render();
    }).catch(function (e) {
      g.SB.logout();
      renderLogin();
      toast(e.message === '没有权限' ? '这个账号没有档案权限' : ('无法进入：' + (e.message || '网络错误')), 'err');
    });
  }

  /* ---------- 主界面 ---------- */
  function render() {
    el.innerHTML = '';
    var top = h('div', 'card');
    var t = h('h1', null, '人物档案与日记');
    var out = h('button', null, '退出');
    out.style.cssText = 'float:right';
    out.onclick = function () { g.SB.logout(); renderLogin(); };
    t.appendChild(out);
    top.appendChild(t);

    var tabs = h('div', 'row');
    [['write', '随手记'], ['journal', '大日记'], ['person', '人物']].forEach(function (x) {
      var b = h('button', null, x[1]);
      if (state.tab === x[0]) b.className = 'primary';
      b.onclick = function () { state.tab = x[0]; render(); };
      tabs.appendChild(b);
    });
    top.appendChild(tabs);
    el.appendChild(top);

    if (state.tab === 'write') return renderWrite();
    if (state.tab === 'journal') return renderJournal();
    return renderPerson();
  }

  /* ---------- 随手记 ---------- */
  function renderWrite() {
    var c = h('div', 'card');
    c.appendChild(h('h2', null, '随手记'));
    var sel = h('select');
    var o0 = h('option', null, '（不归属任何人，只进大日记）'); o0.value = '';
    sel.appendChild(o0);
    state.people.forEach(function (p) {
      var o = h('option', null, p.name); o.value = p.id;
      if (p.id === state.cur) o.selected = true;
      sel.appendChild(o);
    });
    sel.onchange = function () { state.cur = sel.value || null; };
    var r0 = h('div', 'row');
    r0.appendChild(h('span', 'muted', '归属：')); r0.appendChild(sel);
    c.appendChild(r0);

    var ta = h('textarea'); ta.placeholder = '今天记两句…';
    c.appendChild(ta);

    var btn = h('button', 'primary', '记下');
    btn.onclick = function () {
      if (!ta.value.trim()) { toast('写点什么', 'err'); return; }
      btn.disabled = true;
      rpc('profile_entry_add', {
        p_profile: state.cur || null, p_body: ta.value, p_images: []
      }).then(function () {
        ta.value = ''; toast('已记下', 'ok');
        return rpc('profile_list');
      }).then(function (r) { state.people = r || []; }).catch(function (e) {
        toast('保存失败：' + (e.message || '网络错误'), 'err');
      }).then(function () { btn.disabled = false; });
    };
    var r1 = h('div', 'row'); r1.appendChild(btn);
    c.appendChild(r1);
    el.appendChild(c);
  }

  /* ---------- 第 1 层 · 大日记 ---------- */
  function renderJournal() {
    var c = h('div', 'card');
    c.appendChild(h('h2', null, '大日记（按时间汇集，不分人）'));
    rpc('journal_list', { p_limit: 100, p_offset: 0 }).then(function (rows) {
      rows = rows || [];
      if (!rows.length) { c.appendChild(h('p', 'muted', '还没有内容')); return; }
      var exp = h('button', null, '导出待整理文本');
      exp.onclick = function () { exportText(rows); };
      c.appendChild(exp);

      rows.forEach(function (e2) {
        var it = h('div', 'list');
        var m = h('div', 'meta', new Date(e2.created_at).toLocaleString()
          + (e2.profile_name ? ' · ' + e2.profile_name : ''));
        it.appendChild(m);
        /* 改写过就显示改写后的，并保留原文可对照 */
        var body = h('div', 'pre', e2.polished || e2.body);
        it.appendChild(body);
        if (e2.polished) {
          var det = document.createElement('details');
          det.appendChild(h('summary', 'muted', '看原文'));
          det.appendChild(h('div', 'pre', e2.body));
          it.appendChild(det);
        }
        var pb = h('button', null, '改写');
        pb.style.fontSize = '12px';
        pb.onclick = function () { polish(e2, function () { render(); }); };
        var r = h('div', 'row'); r.appendChild(pb);
        it.appendChild(r);
        c.appendChild(it);
      });
    }).catch(function (e) {
      c.appendChild(h('p', 'err', '读取失败：' + (e.message || '网络错误')));
    });
    el.appendChild(c);
  }

  /* 改写：只润色流畅度，最大程度尊重原文 */
  function polish(e2, done) {
    var box = h('div');
    box.appendChild(h('p', 'muted', '只润色流畅度：理顺句子、修正错别字、口语转书面。'
      + '不要加推断、不要加评价、不要写出原文没有的信息。'));
    var ta = h('textarea'); ta.style.height = '200px';
    ta.value = e2.polished || e2.body;
    box.appendChild(ta);
    var save = h('button', 'primary', '保存改写');
    save.onclick = function () {
      rpc('profile_entry_polish', { p_id: e2.id, p_polished: ta.value })
        .then(function () { toast('已保存（原文保留不动）', 'ok'); close(); done(); })
        .catch(function (e) { toast('失败：' + (e.message || '网络错误'), 'err'); });
    };
    var close = modal('改写', box, save);
  }

  /* ---------- 第 3 层：人物 ---------- */
  function renderPerson() {
    var grid = h('div', 'grid');
    var side = h('div', 'side');
    side.appendChild(h('h2', null, '人物'));
    state.people.forEach(function (p) {
      var it = h('div', 'person' + (p.id === state.cur ? ' on' : ''), p.name);
      it.onclick = function () { state.cur = p.id; render(); };
      side.appendChild(it);
    });
    var add = h('button', null, '+ 新建人物');
    add.style.cssText = 'width:100%;font-size:12px;margin-top:8px';
    add.onclick = function () {
      var n = prompt('人物名');
      if (!n || !n.trim()) return;
      rpc('profile_create', { p_name: n.trim() }).then(function () {
        return rpc('profile_list');
      }).then(function (r) { state.people = r || []; render(); });
    };
    side.appendChild(add);
    grid.appendChild(side);

    var main = h('div', 'main');
    if (!state.cur) {
      main.appendChild(h('p', 'muted', '选一个人物'));
    } else {
      main.appendChild(personBlock(state.cur));
    }
    grid.appendChild(main);
    el.appendChild(grid);
  }

  function personBlock(pid) {
    var wrap = h('div');

    /* 第 2 层 · 小日记 */
    var n1 = h('div', 'card');
    n1.appendChild(h('h2', null, '小日记（归到这个人的条日记）'));
    rpc('profile_notes_get', { p_profile: pid }).then(function (ns) {
      ns = ns || [];
      if (!ns.length) n1.appendChild(h('p', 'muted', '还没有'));
      ns.forEach(function (x) {
        var it = h('div', 'list');
        var m = h('div', 'meta', (x.happened_at ? new Date(x.happened_at).toLocaleDateString() : '时间不详')
          + (x.category ? ' · ' + x.category : ''));
        it.appendChild(m);
        it.appendChild(h('div', 'pre', x.content));
        var d = h('span', 'muted', '删除');
        d.style.cssText = 'cursor:pointer;margin-left:6px;font-size:11px';
        d.onclick = function () {
          rpc('profile_note_del', { p_id: x.id }).then(function () { render(); });
        };
        m.appendChild(d);
        n1.appendChild(it);
      });
    });
    var addNote = h('button', null, '＋ 加一条小日记');
    addNote.style.fontSize = '12px';
    addNote.onclick = function () { addNoteDialog(pid); };
    n1.appendChild(h('div', 'row')).appendChild(addNote);
    wrap.appendChild(n1);

    /* 第 3 层 · 个人档案 */
    var n2 = h('div', 'card');
    n2.appendChild(h('h2', null, '个人档案'));
    rpc('profile_summaries_get', { p_profile: pid }).then(function (ss) {
      ss = ss || [];
      var kinds = [['outline', '大纲概览'], ['detail', '详细数据'],
                   ['timeline', '时间线'], ['category', '分类条目'], ['digest', '结构化摘要']];
      kinds.forEach(function (k) {
        var s = ss.filter(function (x) { return x.kind === k[0]; })[0];
        var sec = h('div');
        sec.style.marginBottom = '10px';
        sec.appendChild(h('div', 'muted', k[1] + (s ? ' · ' + new Date(s.created_at).toLocaleString() : '')));
        sec.appendChild(h('div', 'pre', s ? s.content : '（还没整理过）'));
        n2.appendChild(sec);
      });
    });
    var paste = h('button', null, '粘贴整理结果');
    paste.style.fontSize = '12px';
    paste.onclick = function () { pasteSummary(pid); };
    n2.appendChild(h('div', 'row')).appendChild(paste);
    wrap.appendChild(n2);

    /* 相册 */
    var n3 = h('div', 'card');
    n3.appendChild(h('h2', null, '相册'));
    rpc('profile_album', { p_profile: pid }).then(function (as) {
      if (!as || !as.length) { n3.appendChild(h('p', 'muted', '还没有图片')); return; }
      var row = h('div', 'row');
      as.forEach(function (a) {
        var im = document.createElement('img');
        im.className = 'thumb';
        im.src = 'https://pimryrsxkwyafmponegp.supabase.co/storage/v1/object/public/media/' + a.path;
        row.appendChild(im);
      });
      n3.appendChild(row);
    });
    wrap.appendChild(n3);
    return wrap;
  }

  function addNoteDialog(pid) {
    var box = h('div');
    var cat = h('input'); cat.placeholder = '分类（见面 / 通话 / 工作 / 生活…）';
    var ta = h('textarea'); ta.placeholder = '内容';
    var dt = h('input'); dt.type = 'date';
    box.appendChild(h('p', 'muted', '事发时间记不清就留空，不要编。'));
    box.appendChild(cat); box.appendChild(ta); box.appendChild(dt);
    var save = h('button', 'primary', '保存');
    save.onclick = function () {
      if (!ta.value.trim()) { toast('内容为空', 'err'); return; }
      rpc('profile_note_add', {
        p_profile: pid, p_category: cat.value, p_content: ta.value,
        p_source_ids: [], p_happened_at: dt.value ? (dt.value + 'T00:00:00Z') : null
      }).then(function () { toast('已保存', 'ok'); close(); render(); })
        .catch(function (e) { toast('失败：' + (e.message || '网络错误'), 'err'); });
    };
    var close = modal('加一条小日记', box, save);
  }

  function pasteSummary(pid) {
    var box = h('div');
    var sel = h('select');
    [['outline', '大纲概览'], ['detail', '详细数据'], ['timeline', '时间线'],
     ['category', '分类条目'], ['digest', '结构化摘要']].forEach(function (k) {
      var o = h('option', null, k[1]); o.value = k[0]; sel.appendChild(o);
    });
    box.appendChild(sel);
    var ta = h('textarea'); ta.style.height = '200px';
    ta.placeholder = '把整理结果粘进来…';
    box.appendChild(ta);
    box.appendChild(h('p', 'muted', '每次保存都是新的一版，不会覆盖旧的。'));
    var save = h('button', 'primary', '保存为新的一版');
    save.onclick = function () {
      if (!ta.value.trim()) { toast('内容是空的', 'err'); return; }
      rpc('profile_summary_add', { p_profile: pid, p_kind: sel.value, p_content: ta.value })
        .then(function () { toast('已保存', 'ok'); close(); render(); })
        .catch(function (e) { toast('失败：' + (e.message || '网络错误'), 'err'); });
    };
    var close = modal('保存整理结果', box, save);
  }

  function exportText(rows) {
    var lines = ['# 大日记（待整理）', ''];
    rows.slice().reverse().forEach(function (e2, i) {
      lines.push((i + 1) + '. [' + new Date(e2.created_at).toLocaleString() + ']'
        + (e2.profile_name ? '（' + e2.profile_name + '）' : ''));
      lines.push(e2.polished || e2.body);
      lines.push('');
    });
    var box = h('div');
    var ta = h('textarea'); ta.style.height = '300px'; ta.value = lines.join('\n');
    box.appendChild(ta);
    var cb = h('button', null, '复制');
    cb.onclick = function () {
      ta.select();
      try { document.execCommand('copy'); toast('已复制', 'ok'); }
      catch (e) { toast('复制失败，请手动选中', 'err'); }
    };
    box.appendChild(cb);
    modal('复制这段交给 AI 整理', box, null);
  }

  function modal(title, body, okBtn) {
    var mask = h('div');
    mask.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.35);z-index:50;'
      + 'display:flex;align-items:center;justify-content:center;padding:20px';
    var card = h('div', 'card');
    card.style.cssText = 'width:100%;max-width:560px;max-height:80vh;overflow:auto;background:#fff';
    card.appendChild(h('h2', null, title));
    card.appendChild(body);
    var row = h('div', 'row');
    if (okBtn) row.appendChild(okBtn);
    var cancel = h('button', null, '关闭');
    var close = function () { mask.remove(); };
    cancel.onclick = close;
    row.appendChild(cancel);
    card.appendChild(row);
    mask.appendChild(card);
    mask.onclick = function (e) { if (e.target === mask) close(); };
    document.body.appendChild(mask);
    return close;
  }

  boot();
})(window);
