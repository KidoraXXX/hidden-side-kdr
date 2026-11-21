"""
把 dist/ 打包成可用于 Cloudflare Pages 直接上传的 zip。

为什么不用 Windows 的 Compress-Archive：
它会把条目名写成反斜杠（about\\index.html）。Cloudflare Pages 运行在 Linux，
会把这些当成"文件名里带反斜杠的单个文件"，导致除首页外全部 404、图片加载失败。
本脚本强制使用正斜杠。

用法：
    py scripts/pack-zip.py [输出路径]
默认输出到仓库根目录的 kdrefrain-static.zip。
"""
import os
import sys
import zipfile

here = os.path.dirname(os.path.abspath(__file__))
dist = os.path.normpath(os.path.join(here, '..', 'dist'))
out = sys.argv[1] if len(sys.argv) > 1 else os.path.normpath(os.path.join(here, '..', '..', 'kdrefrain-static.zip'))

if not os.path.isdir(dist):
    raise SystemExit(f'dist 目录不存在：{dist}，请先运行 npm run build')

if os.path.exists(out):
    os.remove(out)

count = 0
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as archive:
    for root, dirs, files in os.walk(dist):
        dirs.sort()
        for name in sorted(files):
            full = os.path.join(root, name)
            # 统一用正斜杠，这是 zip 规范要求的路径分隔符
            arc = os.path.relpath(full, dist).replace(os.sep, '/')
            archive.write(full, arc)
            count += 1

print(f'已打包 {count} 个文件 -> {out}')
