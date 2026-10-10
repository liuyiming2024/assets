#!/usr/bin/env python3
"""把关键输出写回仓库，供外部查阅。

为什么需要这个：沙箱下载不到 Actions 的产物（artifact 存储被网络策略挡），
也读不到 run 的日志正文。唯一能读回来的通道就是把内容写成文件推回仓库。

用独立脚本而不是 workflow 里内联的 heredoc ——
嵌套 heredoc 缩进稍错就静默不执行，而 continue-on-error 会把失败
包装成 success，表面看着正常实际什么都没写。
"""
import os, sys, json, base64, glob, urllib.request

REPO = os.environ.get('GITHUB_REPOSITORY', 'liuyiming2024/assets')
TOK = os.environ.get('GH_TOKEN')
DIST = sys.argv[1] if len(sys.argv) > 1 else 'dist'


def api(method, path, body=None, raw=False):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        'https://api.github.com/repos/%s/contents/%s' % (REPO, path),
        method=method, data=data,
        headers={'Authorization': 'Bearer ' + TOK,
                 'Accept': 'application/vnd.github+json',
                 'User-Agent': 'diag'})
    try:
        r = urllib.request.urlopen(req, timeout=60)
        return json.load(r)
    except Exception as e:
        return {'_err': str(e)[:200]}


lines = []
lines.append('run: %s' % os.environ.get('GITHUB_RUN_ID', '?'))
lines.append('target: %s' % os.environ.get('TARGET', '?'))
lines.append('')
lines.append('--- dist 内容 ---')
try:
    for f in sorted(glob.glob(DIST + '/*')):
        lines.append('  %s  %d bytes' % (f, os.path.getsize(f)))
except Exception as e:
    lines.append('  (读取失败: %s)' % e)
lines.append('')
lines.append('--- _fetched.json ---')
try:
    lines.append(json.dumps(json.load(open(DIST + '/_fetched.json', encoding='utf-8')),
                            ensure_ascii=False, indent=2))
except Exception as e:
    lines.append('(无: %s)' % e)
lines.append('')
lines.append('--- 发布日志 _publish.log ---')
try:
    lines.append(open(DIST + '/_publish.log', encoding='utf-8').read())
except Exception as e:
    lines.append('(无: %s)' % e)
lines.append('')
lines.append('--- manifest.json ---')
try:
    lines.append(open('manifest.json', encoding='utf-8').read())
except Exception as e:
    lines.append('(无: %s)' % e)

content = '\n'.join(lines)
path = '_log.txt'

cur = api('GET', path)
body = {'message': '更新抓取日志', 'content': base64.b64encode(content.encode()).decode()}
if isinstance(cur, dict) and cur.get('sha'):
    body['sha'] = cur['sha']
r = api('PUT', path, body)
if isinstance(r, dict) and r.get('_err'):
    print('写回失败：%s' % r['_err'])
    sys.exit(1)
print('日志已写回 %s（%d 字节）' % (path, len(content)))
