"""
把整个 static-site 通过 GitHub REST API 推送到仓库，不依赖 git 命令。

为什么不用 git push：
本机到 github.com 的 443 经常超时，但 api.github.com 可以访问。
脚本用 Git Data API（blob → tree → commit → ref）一次提交完成，
空仓库也能直接创建目标分支（默认 master）。

用法：
    py static-site/scripts/push-to-github.py

凭据（按顺序查找，二选一）：
    1. 环境变量 GITHUB_CONTENT_TOKEN
    2. backend/backend/env.local.json（已 gitignore）中的同名键
仓库与分支同样支持 GITHUB_CONTENT_REPO / GITHUB_CONTENT_BRANCH 覆盖。

可重复运行：每次基于目标分支最新提交做增量覆盖，
不会删除仓库里由后台同步写入的文章 md。
"""
import base64
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"
SKIP_DIRS = {"node_modules", "dist", ".astro", ".git"}

here = os.path.dirname(os.path.abspath(__file__))
site_root = os.path.normpath(os.path.join(here, ".."))
env_path = os.path.normpath(
    os.path.join(site_root, "..", "backend", "backend", "env.local.json")
)


def setting(key, default=""):
    value = os.environ.get(key, "").strip()
    if value:
        return value
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as file:
            value = str(json.load(file).get(key, "")).strip()
            if value:
                return value
    return default


token = setting("GITHUB_CONTENT_TOKEN")
repo = setting("GITHUB_CONTENT_REPO", "KidoraXXX/hidden-side-kdr")
branch = setting("GITHUB_CONTENT_BRANCH", "master")

if not token:
    raise SystemExit(
        "缺少 GITHUB_CONTENT_TOKEN：请设置环境变量，或在 "
        f"{env_path} 中填入。\n"
        "Fine-grained PAT 只需目标仓库的 Contents: Read and write。"
    )


def call(method, path, payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "KDR-Blog-Push",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read()
            return response.status, (json.loads(body) if body else None)
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", "replace")


def expect(status, body, allowed, action):
    if status not in allowed:
        raise SystemExit(f"{action}失败（HTTP {status}）：{body}")


def initialize_empty_repo():
    """空仓库无法直接使用 Git Data API（blobs 返回 409）。

    先用 Contents API 建一个 README，让仓库拥有第一个提交和默认分支，
    后面的 blob/tree/commit 才能工作。
    """
    readme = (
        "# KDR 的秘境图书馆\n\n"
        "静态站源码位于 `static-site/`，文章由后端同步写入。\n"
    )
    status, body = call(
        "PUT",
        f"/repos/{repo}/contents/README.md",
        {
            "message": "init: repository",
            "content": base64.b64encode(readme.encode("utf-8")).decode("ascii"),
        },
    )
    if status not in (200, 201):
        raise SystemExit(f"初始化空仓库失败（HTTP {status}）：{body}")
    print("空仓库已初始化（默认分支 + README）")


def ref_commit(branch_name):
    """返回分支最新提交的 sha；分支不存在时返回 None。"""
    status, body = call("GET", f"/repos/{repo}/git/ref/heads/{branch_name}")
    if status == 200:
        return body["object"]["sha"]
    if status in (404, 409):
        return None
    raise SystemExit(f"读取分支 {branch_name} 失败（HTTP {status}）：{body}")


# 1. 收集文件（排除依赖、构建产物）
files = []
for root, dirs, names in os.walk(site_root):
    dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
    for name in sorted(names):
        full = os.path.join(root, name)
        relative = os.path.relpath(full, site_root).replace(os.sep, "/")
        files.append((relative, full))

if not files:
    raise SystemExit(f"没有找到可推送的文件：{site_root}")

# 2. 上传 blob
entries = []
initialized = False
for relative, full in files:
    with open(full, "rb") as file:
        content = base64.b64encode(file.read()).decode("ascii")
    status, body = call(
        "POST",
        f"/repos/{repo}/git/blobs",
        {"content": content, "encoding": "base64"},
    )
    if status == 409 and not initialized:
        initialize_empty_repo()
        initialized = True
        status, body = call(
            "POST",
            f"/repos/{repo}/git/blobs",
            {"content": content, "encoding": "base64"},
        )
    expect(status, body, (201,), f"上传 {relative} ")
    entries.append(
        {
            "path": f"static-site/{relative}",
            "mode": "100644",
            "type": "blob",
            "sha": body["sha"],
        }
    )
    print(f"  已上传 {relative}")

# 3. 读取目标分支当前状态；仓库刚初始化时基于默认分支创建
target_sha = ref_commit(branch)
target_exists = target_sha is not None
parent = target_sha
if parent is None:
    status, repo_info = call("GET", f"/repos/{repo}")
    default_branch = repo_info.get("default_branch") if isinstance(repo_info, dict) else None
    if default_branch and default_branch != branch:
        parent = ref_commit(default_branch)
        if parent:
            print(f"目标分支 {branch} 不存在，将基于 {default_branch} 创建")
    if parent is None:
        print(f"目标分支 {branch} 不存在，将创建它")

base_tree = None
if parent:
    status, commit = call("GET", f"/repos/{repo}/git/commits/{parent}")
    expect(status, commit, (200,), "读取上次提交 ")
    base_tree = commit["tree"]["sha"]

# 4. 建 tree（有父提交时以它为基础，保留后台同步写入的文章）
tree_payload = {"tree": entries}
if base_tree:
    tree_payload["base_tree"] = base_tree
status, tree = call("POST", f"/repos/{repo}/git/trees", tree_payload)
expect(status, tree, (201,), "创建目录树 ")

# 5. 建 commit
message = f"deploy: static-site ({len(entries)} files)"
status, new_commit = call(
    "POST",
    f"/repos/{repo}/git/commits",
    {
        "message": message,
        "tree": tree["sha"],
        "parents": [parent] if parent else [],
    },
)
expect(status, new_commit, (201,), "创建提交 ")

# 6. 更新或创建分支引用
if target_exists:
    status, body = call(
        "PATCH",
        f"/repos/{repo}/git/refs/heads/{branch}",
        {"sha": new_commit["sha"], "force": False},
    )
    expect(status, body, (200,), "更新分支 ")
else:
    status, body = call(
        "POST",
        f"/repos/{repo}/git/refs",
        {"ref": f"refs/heads/{branch}", "sha": new_commit["sha"]},
    )
    expect(status, body, (201,), "创建分支 ")

print(
    f"\n完成：{len(entries)} 个文件已推送到 {repo} 的 {branch} 分支\n"
    f"提交：{new_commit['sha']}\n"
    f"地址：https://github.com/{repo}/tree/{branch}/static-site"
)
