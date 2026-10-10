#!/usr/bin/env python3
"""把 dist/ 里的文件发成 Release 资产。

用 Release 而不是 git 提交：
  git 里的二进制"只增不减"，clone 一次就再也快不起来了。
  Release 资产不进 git 历史 —— 只有真要用的人才下载那一个文件。

标签默认固定为 latest：可重复运行，重跑不会撞「tag 已存在」。
"""
import os, sys, json, urllib.request, urllib.error, urllib.parse

API = 'https://api.github.com'


def api(method, path, tok, body=None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(API + path, method=method, data=data, headers={
        'Authorization': 'Bearer ' + tok,
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'assets-publish'
    })
    try:
        return json.load(urllib.request.urlopen(req, timeout=60))
    except urllib.error.HTTPError as e:
        return {'_err': e.code, '_body': e.read().decode()[:300]}


def main():
    tok = os.environ.get('GH_TOKEN')
    repo = None
    dist = 'dist'
    tag = 'latest'
    a = sys.argv
    for i, x in enumerate(a):
        if x == '--repo' and i + 1 < len(a): repo = a[i + 1]
        if x == '--dir' and i + 1 < len(a): dist = a[i + 1]
        if x == '--tag' and i + 1 < len(a): tag = a[i + 1]

    if not tok or not repo:
        print('缺少 GH_TOKEN 或 --repo')
        return 1

    meta_p = os.path.join(dist, '_fetched.json')
    files = [f for f in os.listdir(dist) if f != '_fetched.json' and os.path.isfile(os.path.join(dist, f))]
    if not files:
        print('dist/ 是空的，没什么可发')
        return 0

    # 找到或创建 Release。固定 tag → 重跑不会撞「tag 已存在」
    rel = api('GET', '/repos/%s/releases/tags/%s' % (repo, tag), tok)
    if '_err' in rel:
        rel = api('POST', '/repos/%s/releases' % repo, tok, {
            'tag_name': tag, 'name': '运行时资源（%s）' % tag,
            'body': '按需加载的 WASM 运行时。主仓库保持零依赖，这些只在用户主动要用时才下载。',
            'prerelease': True
        })
        print('  已创建 Release %s' % tag)
    if '_err' in rel:
        print('  ✗ 拿不到 Release：', rel.get('_body'))
        return 1

    # 删掉同名旧资产再传新的（Release 资产不允许重名）
    for old in rel.get('assets', []):
        if old['name'] in files:
            api('DELETE', '/repos/%s/releases/assets/%d' % (repo, old['id']), tok)
            print('  已替换旧资产 %s' % old['name'])

    up = rel['upload_url'].split('{')[0]
    ok_n = 0
    for f in files:
        path = os.path.join(dist, f)
        size = os.path.getsize(path)
        with open(path, 'rb') as fh:
            data = fh.read()
        req = urllib.request.Request(
            '%s?name=%s' % (up, urllib.parse.quote(f)), method='POST', data=data,
            headers={'Authorization': 'Bearer ' + tok,
                     'Accept': 'application/vnd.github+json',
                     'Content-Type': 'application/octet-stream',
                     'User-Agent': 'assets-publish'})
        try:
            urllib.request.urlopen(req, timeout=600)
            print('  ✓ %s  %.1f MB' % (f, size / 1048576))
            ok_n += 1
        except Exception as e:
            print('  ✗ %s → %s' % (f, e))

    print('\n发布 %d / %d' % (ok_n, len(files)))
    return 0 if ok_n == len(files) else 1


if __name__ == '__main__':
    sys.exit(main())
