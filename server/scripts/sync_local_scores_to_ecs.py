"""
将本机已发布的曲包目录（server/data/scores 下各子文件夹）同步到阿里云 ECS 上的部署路径。

与 remote_aliyun_deploy.py 相同的环境变量：
  ALIYUN_HOST=8.156.88.121
  ALIYUN_ROOT_PASSWORD=...

可选：
  LOCAL_SCORES_DIR=.../server/data/scores  （默认为本仓库下该路径）
  REMOTE_SCORES_DIR=/opt/new_yuepu/server/data/scores

用法（在仓库根目录）:
  set ALIYUN_ROOT_PASSWORD=你的密码
  python server/scripts/sync_local_scores_to_ecs.py
"""
from __future__ import annotations

import io
import os
import sys
import tarfile
from pathlib import Path

try:
    import paramiko
except ImportError:
    print("请先安装: pip install paramiko", file=sys.stderr)
    raise SystemExit(2) from None

HOST = os.environ.get("ALIYUN_HOST", "8.156.88.121").strip()
PASSWORD = (os.environ.get("ALIYUN_ROOT_PASSWORD") or "").strip()

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_LOCAL = _REPO_ROOT / "server" / "data" / "scores"
LOCAL_SCORES = Path(os.environ.get("LOCAL_SCORES_DIR", str(_DEFAULT_LOCAL))).resolve()
REMOTE_SCORES = os.environ.get(
    "REMOTE_SCORES_DIR",
    "/opt/new_yuepu/server/data/scores",
).strip()


def build_tar_gz() -> bytes:
    if not LOCAL_SCORES.is_dir():
        raise SystemExit(f"本地曲库目录不存在: {LOCAL_SCORES}")

    buf = io.BytesIO()
    count = 0
    with tarfile.open(fileobj=buf, mode="w:gz", format=tarfile.GNU_FORMAT) as tf:
        for p in sorted(LOCAL_SCORES.iterdir()):
            if p.name.startswith("."):
                continue
            if p.name == ".gitkeep" and p.is_file():
                continue
            tf.add(p, arcname=p.name, filter=None)
            count += 1
    if count == 0:
        print(f"警告: {LOCAL_SCORES} 下没有可同步的子目录/文件", file=sys.stderr)
    buf.seek(0)
    return buf.read()


def main() -> int:
    if not PASSWORD:
        print("请设置环境变量 ALIYUN_ROOT_PASSWORD", file=sys.stderr)
        return 2

    try:
        blob = build_tar_gz()
    except SystemExit as e:
        return int(e.code) if isinstance(e.code, int) else 1

    print(f"打包完成: {len(blob)} 字节（来源 {LOCAL_SCORES}）", flush=True)

    last_err = None
    for user in ("root", "ubuntu"):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                HOST,
                username=user,
                password=PASSWORD,
                timeout=45,
                allow_agent=False,
                look_for_keys=False,
            )
        except Exception as e:
            last_err = e
            continue
        try:
            print(f"已连接 {HOST} 用户={user}", flush=True)
            prep = f"mkdir -p {REMOTE_SCORES} && chmod 755 {REMOTE_SCORES}"
            prep_cmd = f"sudo -H {prep}" if user != "root" else prep
            _in, out, err = client.exec_command(prep_cmd, timeout=60)
            _in.close()
            code0 = out.channel.recv_exit_status()
            if code0 != 0:
                print(err.read().decode("utf-8", errors="replace"), file=sys.stderr)
                return 3

            tar_cmd = f"tar -xzf - -C {REMOTE_SCORES}"
            if user != "root":
                tar_cmd = f"sudo tar -xzf - -C {REMOTE_SCORES}"
            stdin, stdout, stderr = client.exec_command(tar_cmd, timeout=600)
            stdin.write(blob)
            stdin.channel.shutdown_write()

            out_b = stdout.read().decode("utf-8", errors="replace")
            err_b = stderr.read().decode("utf-8", errors="replace")
            code = stdout.channel.recv_exit_status()
            if out_b:
                print(out_b, flush=True)
            if err_b:
                print(err_b, file=sys.stderr, flush=True)
            if code != 0:
                return code

            print(f"已解压到远端: {REMOTE_SCORES}", flush=True)
            return 0
        finally:
            client.close()

    print(f"SSH 失败: {last_err}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
