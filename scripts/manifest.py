#!/usr/bin/env python3
"""生成 manifest.json —— 客户端据此知道有哪些资源、多大、怎么下。

⚠ 硬约束：url 必须是**文件直链**，不能是网页地址。
  网页地址会下到 HTML，文件不到 1KB 却"成功了" —— 这种假成功最难查。
  GitHub 的 release 直链形如 releases/latest/download/xxx.wasm，本身就是文件。
"""
import os, sys, json, datetime

REPO_DEFAULT = 'liuyiming2024/assets'


def main():
    repo = os.environ.get('GITHUB_REPOSITORY', REPO_DEFAULT)
    dist = 'dist'
    a = sys.argv
    for i, x in enumerate(a):
        if x == '--repo' and i + 1 < len(a): repo = a[i + 1]
        if x == '--dir' and i + 1 < len(a): dist = a[i + 1]

    meta_p = os.path.join(dist, '_fetched.json')
    items = []
    if os.path.exists(meta_p):
        items = json.load(open(meta_p, encoding='utf-8'))
    # 抓不到的不该出现在清单里 —— 清单写着"可下载"，点下去却是 404，
    # 比没有这一项更糟。用 dist 里的真实文件再过滤一道。
    items = [it for it in items
             if os.path.exists(os.path.join(dist, it['name']))
             and os.path.getsize(os.path.join(dist, it['name'])) == it['size']]

    base = 'https://github.com/%s/releases/latest/download/' % repo
    for it in items:
        it['url'] = base + it['name']          # 文件直链，不是网页地址
        it.pop('src', None)

    man = {
        'updated': datetime.date.today().isoformat(),
        'note': [
            '按需加载的 WASM 运行时。主仓库保持零依赖，',
            '这些只在用户主动要用某个语言时才下载。',
            '下载后请自行缓存（Cache Storage / IndexedDB），之后离线也能用。'
        ],
        'usage': '首次需要联网；缓存后离线可用。加载请放 Web Worker，否则会白屏好几秒。',
        'files': items
    }

    open('manifest.json', 'w', encoding='utf-8').write(
        json.dumps(man, ensure_ascii=False, indent=2))
    print('  清单已生成：%d 个文件' % len(items))
    return 0


if __name__ == '__main__':
    sys.exit(main())
