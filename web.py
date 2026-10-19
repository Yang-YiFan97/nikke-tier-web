import os
import json
import base64
from html import escape
from pathlib import Path

import streamlit as st

import red
from db_manager import equip_db_manager, EQUIP_DB_PATH

st.set_page_config(
    page_title="NIKKE 工具箱", page_icon="🔴", layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(f"<style>{Path(__file__).with_name('styles.css').read_text()}</style>", unsafe_allow_html=True)

def page_header(title, subtitle, status):
    st.markdown(
        f'<header class="tool-header"><div><div class="header-title">'
        f'<span class="nikke-logo">NIKKE</span><h1>{escape(title)}</h1></div>'
        f'<p>{escape(subtitle)}</p></div><span class="status-pill">'
        f'<span class="status-dot"></span>{escape(status)}</span></header>',
        unsafe_allow_html=True,
    )


def section_heading(title, subtitle="", count=""):
    st.markdown(
        f'<div class="section-heading"><div><span class="section-icon">▤</span>'
        f'<h2>{escape(title)}</h2><span class="section-subtitle">{escape(subtitle)}</span>'
        f'</div><span class="section-count">{escape(count)}</span></div>',
        unsafe_allow_html=True,
    )


def number(value):
    return f"{value:.2f}".rstrip("0").rstrip(".")


with st.sidebar:
    st.markdown('<div class="sidebar-brand"><span class="nikke-logo">NIKKE</span>'
                '<h2>工具箱</h2><p>NIKKE TOOLS</p></div>', unsafe_allow_html=True)
    st.markdown('<div class="nav-heading">▧ <span>功能导航</span></div>', unsafe_allow_html=True)
    app_mode = st.radio("功能导航", ["红球表查询", "装备词条查询"],
                        format_func=lambda x: "🔴　红球表查询" if x == "红球表查询" else "◯　装备词条查询",
                        label_visibility="collapsed")
    st.divider()
    st.markdown('<div class="sidebar-footer">NIKKE TOOLS</div>', unsafe_allow_html=True)

if app_mode == "红球表查询":
    if "last_chapter" not in st.session_state:
        st.session_state.last_chapter = 34

    header_slot = st.empty()

    # The submitted chapter stays active across tab and sidebar reruns.
    with st.container(key="chapter_query"):
        st.markdown('<h2 class="query-heading">章节查询</h2>', unsafe_allow_html=True)
        with st.form("red_query_form", border=False):
            col_input, col_action = st.columns([2.15, 1], vertical_alignment="bottom")
            with col_input:
                chapter_num = st.number_input(
                    "输入章节数", min_value=1, max_value=60,
                    value=st.session_state.last_chapter, step=1,
                    help="计算在不漏怪通关该普通章节时，对应的困难关卡与基地等级",
                )
            with col_action:
                query_btn = st.form_submit_button("⌕  查询红球节点", type="primary", width="stretch")
        if query_btn:
            st.session_state.last_chapter = int(chapter_num)
        chapter = st.session_state.last_chapter
        nodes = None
        if not os.path.exists(red.STAGE_DB) or not os.path.exists(red.PROD_DB):
            st.error(f"未找到关卡数据库 {red.STAGE_DB} 或 {red.PROD_DB}，请确认运行目录。")
        else:
            nodes = red.generate_chapter_nodes(chapter)
            if nodes:
                st.success(f"已生成【普通第 {chapter} 章】红球节点列表")
            else:
                st.warning(f"未在数据库中检索到第 {chapter} 章的关卡数据。")

    with header_slot.container():
        page_header("基地红球产出查询", "OUTPOST CORE DUST · 基地收益与关卡节点", f"普通第 {chapter} 章")

    if nodes:
        levels = [item["target_level"] for item in nodes]
        rates = [item["actual_dust"] for item in nodes]
        st.markdown(
            '<div class="stats-grid">'
            f'<div class="stat-card"><div class="stat-label">节点数量</div><div class="stat-value">{len(nodes)} <small>个</small></div></div>'
            f'<div class="stat-card orange"><div class="stat-label">基地等级</div><div class="stat-value">Lv.{min(levels)} - {max(levels)}</div></div>'
            f'<div class="stat-card teal"><div class="stat-label">芯尘速率</div><div class="stat-value">{number(min(rates))} - {number(max(rates))} <small>个/h</small></div></div>'
            '</div>', unsafe_allow_html=True,
        )
        with st.container(key="node_details"):
            section_heading("红球节点明细", "// NODE LIST", f"共 {len(nodes)} 个节点")
            tab_table, tab_image = st.tabs(["▥　结构化数据表", "▧　原版卡片图片"])
            with tab_table:
                rows = "".join(
                    f'<tr><td><span class="row-number">{index:02d}</span></td>'
                    f'<td>{escape(str(item["stage_name"]))}</td>'
                    f'<td>Lv.{item["target_level"]}</td>'
                    f'<td class="dust-rate">{number(item["actual_dust"])}</td></tr>'
                    for index, item in enumerate(nodes, 1)
                )
                st.markdown(
                    '<div class="node-table-wrap"><table class="node-table"><thead><tr>'
                    '<th>序号</th><th>困难战役关卡</th><th>对应基地等级</th><th>芯尘速率（个/h）</th>'
                    f'</tr></thead><tbody>{rows}</tbody></table></div>', unsafe_allow_html=True,
                )
            with tab_image:
                cq_code = red.render_image(chapter, nodes)
                img_bytes = base64.b64decode(cq_code.split("base64://")[-1].rstrip("]"))
                st.image(img_bytes, caption=f"第 {chapter} 章红球卡片", width="content")
            st.markdown('<div class="panel-footer"><span>OUTPOST DATABASE</span><span>NIKKE TOOLS</span></div>', unsafe_allow_html=True)
else:
    page_header("角色装备词条总览", "EQUIPMENT OVERVIEW · 角色词条与属性加成", "装备数据库")
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
