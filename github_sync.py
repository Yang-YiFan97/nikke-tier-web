import base64
import os
import requests
import streamlit as st

def push_db_to_github(db_relative_path="assets/装备词条.db", commit_message="Update 装备词条.db from web"):
    """
    通过 GitHub API 将更新后的 .db 文件提交到仓库中
    """
    token = st.secrets.get("GITHUB_TOKEN", os.getenv("GITHUB_TOKEN"))
    repo = st.secrets.get("GITHUB_REPO", "Yang-YiFan97/nikke-tier-web")

    if not token:
        st.warning("⚠️ 未检测到 GITHUB_TOKEN，数据未持久化至 GitHub。")
        return False

    url = f"https://api.github.com/repos/{repo}/contents/{db_relative_path}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    try:
        # 1. 获取目标文件当前的 SHA（GitHub API 更新文件必须传入原文件的 sha）
        get_res = requests.get(url, headers=headers, timeout=10)
        sha = None
        if get_res.status_code == 200:
            sha = get_res.json().get("sha")

        # 2. 读取本地写入的 .db 文件二进制数据并转为 Base64
        if not os.path.exists(db_relative_path):
            st.error(f"本地未找到数据库文件: {db_relative_path}")
            return False

        with open(db_relative_path, "rb") as f:
            content_bytes = f.read()
            b64_content = base64.b64encode(content_bytes).decode("utf-8")

        # 3. 构造提交负载
        payload = {
            "message": commit_message,
            "content": b64_content,
            "branch": "main"
        }
        if sha:
            payload["sha"] = sha

        # 4. PUT 请求更新文件
        put_res = requests.put(url, headers=headers, json=payload, timeout=15)
        return put_res.status_code in [200, 201]

    except Exception as e:
        st.error(f"网络同步异常: {str(e)}")
        return False