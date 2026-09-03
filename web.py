import os
import json
import base64
import pandas as pd
import streamlit as st

# 引入项目业务与数据库管理器
import red
from db_manager import equip_db_manager, EQUIP_DB_PATH

# -----------------------------------------------------------------------------
# 页面基础配置
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="NIKKE 工具箱",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -----------------------------------------------------------------------------
# 左侧导航栏 (Sidebar Navigation)
# -----------------------------------------------------------------------------
st.sidebar.title("📌 功能导航")
app_mode = st.sidebar.radio(
    "请选择功能页面：",
    ["红球表查询", "装备词条查询"],
    index=0
)
st.sidebar.markdown("---")

# =============================================================================
# 功能页面 1：红球表查询
# =============================================================================
if app_mode == "红球表查询":
    st.title("🔴 基地红球产出查询")
    st.caption("基于关卡节点与基地等级，快速计算普通关通关下的困难关推进与芯尘速率里程碑")

    # 使用 st.form 包裹，实现敲回车键自动提交查询
    with st.form("red_query_form", border=False):
        col_input, col_action = st.columns([2, 1])
        with col_input:
            chapter_num = st.number_input(
                "输入章节数",
                min_value=1,
                max_value=60,
                value=st.session_state.get("last_chapter", 34),
                step=1,
                help="计算在不漏怪通关该普通章节时，对应的困难关卡与基地等级"
            )
        with col_action:
            st.write("")
            st.write("")
            query_btn = st.form_submit_button("🔍 查询红球节点", use_container_width=True)

    # 首次进入页面或用户按回车/点击按钮时触发
    if query_btn or "last_chapter" not in st.session_state:
        st.session_state.last_chapter = int(chapter_num)
        
        # 验证底层数据库文件是否存在
        if not os.path.exists(red.STAGE_DB) or not os.path.exists(red.PROD_DB):
            st.error(f"⚠️ 未找到关卡数据库 `{red.STAGE_DB}` 或 `{red.PROD_DB}`，请确认文件已上传至运行目录。")
        else:
            with st.spinner("正在计算关卡与红球数据..."):
                nodes = red.generate_chapter_nodes(int(chapter_num))
            
            if not nodes:
                st.warning(f"⚠️ 未在数据库中检索到第 {chapter_num} 章的关卡数据。")
            else:
                st.success(f"已生成【普通第 {chapter_num} 章】红球节点列表")

                # 选项卡展示
                tab_table, tab_image = st.tabs(["📊 结构化数据表", "🖼️ 原版卡片图片"])

                with tab_table:
                    # 使用标准 Markdown 语法排版，避免 HTML 转义问题与任何内部滚动条
                    md_lines = [
                        "| 困难战役关卡 | 对应基地等级 | 芯尘速率 (个/h) |",
                        "| :--- | :--- | :--- |"
                    ]
                    for item in nodes:
                        dust = item["actual_dust"]
                        dust_display = int(dust) if dust == int(dust) else f"{dust:.2f}".rstrip('0').rstrip('.')
                        md_lines.append(f"| **{item['stage_name']}** | Lv.{item['target_level']} | `{dust_display}` |")
                    
                    st.markdown("\n".join(md_lines))

                with tab_image:
                    with st.spinner("正在渲染卡片..."):
                        cq_code = red.render_image(int(chapter_num), nodes)
                        b64_str = cq_code.split("base64://")[-1].rstrip("]")
                        img_bytes = base64.b64decode(b64_str)
                        st.image(img_bytes, caption=f"第 {chapter_num} 章红球卡片", use_container_width=False)

# =============================================================================
# 功能页面 2：装备词条查询
# =============================================================================
elif app_mode == "装备词条查询":
    st.title("🛡️ 角色装备词条总览")
    st.caption("在线检索并查看已录入的角色词条与 0 阶/总属性加成")

    if not os.path.exists(EQUIP_DB_PATH):
        st.info("⚠️ 数据库 `assets/装备词条.db` 尚未初始化或不存在任何数据。")
    else:
        conn = equip_db_manager.get_connection()
        cursor = conn.cursor()
        
        # 读取指挥官列表
        cursor.execute("SELECT DISTINCT user_id FROM character_equips")
        user_rows = cursor.fetchall()
        user_list = [r[0] for r in user_rows if r[0]]

        if not user_list:
            st.info("数据库中暂无指挥官装备记录。")
            conn.close()
        else:
            selected_user = st.sidebar.selectbox("👤 选择指挥官", user_list)

            # 查询角色统计数据
            cursor.execute("""
                SELECT char_name, stats_json, updated_at 
                FROM character_stats 
                WHERE user_id = ? 
                ORDER BY updated_at DESC
            """, (selected_user,))
            stats_rows = cursor.fetchall()
            conn.close()

            if not stats_rows:
                st.warning("该指挥官名下暂无角色汇总数据。")
            else:
                search_kw = st.text_input("🔍 搜索角色名称：", placeholder="输入角色名过滤...")
                
                display_records = []
                for char_name, stats_json, updated_at in stats_rows:
                    if search_kw and search_kw.strip().lower() not in char_name.lower():
                        continue
                    
                    stats_dict = json.loads(stats_json) if stats_json else {}
                    display_records.append({
                        "角色": char_name,
                        "更新时间": updated_at,
                        "属性汇总详情": stats_dict
                    })

                st.markdown(f"共检索到 **{len(display_records)}** 个角色记录")
                
                for item in display_records:
                    with st.expander(f"📌 {item['角色']} (最近更新: {item['更新时间']})", expanded=False):
                        stats = item["属性汇总详情"]
                        if not stats:
                            st.write("暂无属性汇总。")
                        else:
                            col_s1, col_s2 = st.columns(2)
                            with col_s1:
                                st.markdown("##### 🌟 0 阶有效词条属性")
                                s0 = stats.get("0阶", stats.get("tier0", {}))
                                if s0:
                                    for k, v in s0.items():
                                        st.write(f"- **{k}**: `{v}`")
                                else:
                                    st.caption("无 0 阶属性记录")
                            with col_s2:
                                st.markdown("##### ⚡ 总属性统计")
                                s_all = stats.get("总属性", stats.get("total", {}))
                                if s_all:
                                    for k, v in s_all.items():
                                        st.write(f"- **{k}**: `{v}`")
                                else:
                                    st.caption("无总属性记录")
