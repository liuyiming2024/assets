/* 极简 Supabase 客户端 —— 本项目独立实现，不引用其他项目的代码。
   只做三件事：登录、调 RPC、登出。
   鉴权走"统一账号体系"（同一个账号服务），但数据读写全部走本项目自己的函数。 */
(function (g) {
  'use strict';
  var URL = 'https://pimryrsxkwyafmponegp.supabase.co';
  var KEY = 'sb_publishable_jPrK6j5l9NGbnLKcytTegg_di1njO8t';
  var TOKEN_KEY = 'archive.token';
  var token = null;

  try { token = localStorage.getItem(TOKEN_KEY) || null; } catch (e) { }

  function authHeader() { return 'Bearer ' + (token || KEY); }

  function rpc(name, args) {
    return fetch(URL + '/rest/v1/rpc/' + name, {
      method: 'POST',
      headers: {
        'apikey': KEY,
        'Authorization': authHeader(),
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(args || {})
    }).then(function (r) {
      return r.text().then(function (t) {
        var d = null;
        try { d = t ? JSON.parse(t) : null; } catch (e) { d = t; }
        if (!r.ok) {
          var msg = (d && (d.message || d.msg)) || ('请求失败 ' + r.status);
          throw new Error(msg);
        }
        return d;
      });
    });
  }

  function login(nick, pwd) {
    return rpc('user_login', { p_nick: nick, p_pwd: pwd }).then(function (d) {
      var tk = d && (d.token || (d.data && d.data.token));
      if (!tk) throw new Error('登录没返回凭证');
      token = tk;
      try { localStorage.setItem(TOKEN_KEY, tk); } catch (e) { }
      return true;
    });
  }

  function logout() {
    token = null;
    try { localStorage.removeItem(TOKEN_KEY); } catch (e) { }
  }

  g.SB = {
    rpc: rpc, login: login, logout: logout,
    hasToken: function () { return !!token; },
    token: function () { return token; }
  };
})(window);
