#!/usr/bin/env python3
"""把关键输出写回仓库，供外部查阅。

为什么需要这个：沙箱下载不到 Actions 的产物（artifact 存储被网络策略挡），
也读不到 run 的日志正文。唯一能读回来的通道就是把内容写成文件推回仓库。

用独立脚本而不是 workflow 里内联的 heredoc ——
嵌套 heredoc 缩进稍错就静默不执行，而 continue-on-error 会把失败
包装成 success，表面看着正常实际什么都没写。

用法：
  python3 scripts/diag.py dist                   # 清单/许可证 + 失败诊断日志
  python3 scripts/diag.py dist --manifest-only  # 只写清单/许可证（job 成功时）

⚠ 日志固定写 _diag/last-run.txt 且覆盖，不按 run id 追加：
   早期每次抓取都往根目录写 _log.txt，仓库里堆了一堆一次性日志。
   现在成功时不写日志，失败时也只留最后一次。见 fetch.yml 的两个写回步骤。
"""
import os, sys, json, base64, glob, urllib.request

REPO = os.environ.get('GITHUB_REPOSITORY', 'liuyiming2024/assets')
TOK = os.environ.get('GH_TOKEN')
DIST = sys.argv[1] if len(sys.argv) > 1 else 'dist'
MANIFEST_ONLY = '--manifest-only' in sys.argv


def api(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        'https://api.github.com/repos/%s/contents/%s' % (REPO, path),
        method=method, data=data,
        headers={'Authorization': 'Bearer ' + TOK,
                 'Accept': 'application/vnd.github+json',
                 'User-Agent': 'diag'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except Exception as e:
        return {'_err': str(e)[:200]}


def write_back(rel_path, text, message):
    """覆盖式写回一个文本文件。文件不存在时 GET 返回 _err，PUT 会创建。"""
    cur = api('GET', rel_path)
    body = {'message': message,
            'content': base64.b64encode(text.encode('utf-8')).decode()}
    if isinstance(cur, dict) and cur.get('sha'):
        body['sha'] = cur['sha']
    r = api('PUT', rel_path, body)
    if isinstance(r, dict) and r.get('_err'):
        print('  ✗ %s 写回失败：%s' % (rel_path, r['_err']))
        return False
    print('  ✓ %s 已写回' % rel_path)
    return True


# ---- 清单与聚合许可证：只在 Actions 里生成，不写回外部永远读不到 ----
# manifest.py 末尾会调用 gen_license.py 重生成 LICENSE；两者必须一起写回，
# 否则「清单变了但版权没认领」—— README 里把这条写成合规底线。
for rel_path, msg in [('manifest.json', '更新资源清单'),
                      ('LICENSE', '更新聚合许可证')]:
    try:
        write_back(rel_path, open(rel_path, encoding='utf-8').read(), msg)
    except OSError as e:
        print('  ⚠ %s 不存在，跳过：%s' % (rel_path, e))

if MANIFEST_ONLY:
    sys.exit(0)

# ---- 失败诊断日志 ----
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
lines.append('--- 抓取日志 _fetch.log ---')
try:
    lines.append(open(DIST + '/_fetch.log', encoding='utf-8').read())
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
if not write_back('_diag/last-run.txt', content, '记录最近一次抓取失败'):
    sys.exit(1)
print('日志已写回 _diag/last-run.txt（%d 字节）' % len(content))
