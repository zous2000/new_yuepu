"""
从本机经 SSH 在阿里云 ECS 上：释放 8000、停 Docker（若有）、更新代码并以 systemd 运行 uvicorn。

- 已有 /opt/new_yuepu 且为 Git 仓库：git fetch + reset --hard，不删目录；
  server/data/scores 在 .gitignore 中，不会被 reset 清空。
- 目录存在但非 Git：先备份 server/data/scores，再删除并 clone，最后拷回曲谱。
- 首次部署：直接 shallow clone。

用法:
  set ALIYUN_ROOT_PASSWORD=你的密码
  python server/scripts/remote_aliyun_deploy.py

可选: ALIYUN_HOST  REPO_URL  YUEPU_APP_TOKEN
"""
from __future__ import annotations

import base64
import os
import sys
import textwrap

try:
    import paramiko
except ImportError:
    print("请先安装: pip install paramiko", file=sys.stderr)
    raise SystemExit(2) from None

HOST = os.environ.get("ALIYUN_HOST", "8.156.88.121").strip()
PASSWORD = (os.environ.get("ALIYUN_ROOT_PASSWORD") or "").strip()
REPO = os.environ.get("REPO_URL", "https://github.com/zous2000/new_yuepu.git").strip()
DEPLOY_DIR = "/opt/new_yuepu"
APP_TOKEN = (os.environ.get("YUEPU_APP_TOKEN") or "dev-app-token-change-me").strip()


def build_remote_script() -> str:
    unit = textwrap.dedent(
        f"""\
        [Unit]
        Description=Yuepu Score Server (FastAPI)
        After=network.target

        [Service]
        Type=simple
        User=root
        WorkingDirectory={DEPLOY_DIR}/server
        Environment=APP_TOKEN={APP_TOKEN}
        ExecStart={DEPLOY_DIR}/server/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
        Restart=always
        RestartSec=3

        [Install]
        WantedBy=multi-user.target
        """
    ).strip()
    unit_b64 = base64.b64encode(unit.encode("utf-8")).decode("ascii")

    return textwrap.dedent(
        f"""
        set -euxo pipefail
        export DEBIAN_FRONTEND=noninteractive

        apt-get update -qq
        apt-get install -y git python3 python3-venv python3-pip curl ffmpeg

        if command -v fuser >/dev/null 2>&1; then fuser -k 8000/tcp || true; fi
        if command -v lsof >/dev/null 2>&1; then
          for p in $(lsof -ti:8000 2>/dev/null || true); do kill -9 "$p" || true; done
        fi

        if command -v docker >/dev/null 2>&1; then
          docker stop $(docker ps -q) 2>/dev/null || true
        fi

        systemctl stop yuepu-server 2>/dev/null || true

        if [ -d "{DEPLOY_DIR}/.git" ]; then
          cd "{DEPLOY_DIR}"
          git remote set-url origin "{REPO}" || true
          git fetch --depth 1 origin main
          git checkout -f main
          git reset --hard FETCH_HEAD
        elif [ -d "{DEPLOY_DIR}" ]; then
          BACKUP_DIR=$(mktemp -d)
          if [ -d "{DEPLOY_DIR}/server/data/scores" ]; then
            cp -a "{DEPLOY_DIR}/server/data/scores/." "$BACKUP_DIR/" || true
          fi
          rm -rf "{DEPLOY_DIR}"
          git clone --depth 1 "{REPO}" "{DEPLOY_DIR}"
          mkdir -p "{DEPLOY_DIR}/server/data/scores"
          cp -a "$BACKUP_DIR/." "{DEPLOY_DIR}/server/data/scores/" 2>/dev/null || true
          rm -rf "$BACKUP_DIR"
        else
          mkdir -p "$(dirname "{DEPLOY_DIR}")"
          git clone --depth 1 "{REPO}" "{DEPLOY_DIR}"
        fi

        cd "{DEPLOY_DIR}/server"
        if [ ! -d .venv ]; then
          python3 -m venv .venv
        fi
        .venv/bin/pip install -U pip -q
        .venv/bin/pip install -r requirements.txt -q

        echo "{unit_b64}" | base64 -d >/etc/systemd/system/yuepu-server.service

        systemctl daemon-reload
        systemctl enable yuepu-server
        systemctl restart yuepu-server
        sleep 2
        systemctl --no-pager -l status yuepu-server || true
        curl -sS -o /dev/null -w "health_http=%{{http_code}}\\n" http://127.0.0.1:8000/health || true
        """
    )


def main() -> int:
    if not PASSWORD:
        print("请设置环境变量 ALIYUN_ROOT_PASSWORD", file=sys.stderr)
        return 2

    remote = build_remote_script().strip()
    remote_b64 = base64.b64encode(remote.encode("utf-8")).decode("ascii")
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
            # 整段脚本 base64 后管道给 bash，避免 -lc + repr 引号换行问题
            pipe = f"echo {remote_b64} | base64 -d | bash"
            wrap = f"sudo -H {pipe}" if user != "root" else pipe
            stdin, stdout, stderr = client.exec_command(
                wrap,
                get_pty=True,
                timeout=900,
            )
            stdin.close()
            out = stdout.read().decode("utf-8", errors="replace")
            err = stderr.read().decode("utf-8", errors="replace")
            code = stdout.channel.recv_exit_status()
            if out:
                print(out, end="" if out.endswith("\n") else "\n", flush=True)
            if err:
                print(err, end="" if err.endswith("\n") else "\n", file=sys.stderr, flush=True)
            return 0 if code == 0 else code
        finally:
            client.close()

    print(f"SSH 失败（已尝试 root / ubuntu）: {last_err}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
