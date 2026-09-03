import os
import json
import sqlite3
import pandas as pd
import streamlit as st

from db_manager import equip_db_manager
from card_generator import (
    get_character_meta, 
    SHORT_NAME_MAP, 
    calculate_character_stats, 
    load_priority_config, 
    normalize_name
)

# 页面基础配置
st.set_page_config(page_title="妮姬装备词条统计", page_icon="🛡️", layout="wide")
st.title("🛡️ 妮姬装备词条总览面板")

# 属性对应颜色
ELEMENT_COLORS = {
    "燃烧": "background-color: #FFF0F0",
    "水冷": "background-color: #F0F8FF",
    "风压": "background-color: #F0FFF0",
    "电击": "background-color: #F8F0FF",
    "铁甲": "background-color: #F5F5F5",
}
ELEMENT_ORDER = {"燃烧": 1, "水冷": 2, "风压": 3, "电击": 4, "铁甲": 5}

COLUMNS = [
    ("优越", "优越代码伤害增加"),
    ("攻击", "攻击力增加"),
    ("装弹", "最大装弹数增加"),
    ("暴伤", "暴击伤害增加"),
    ("暴率", "暴击率增加"),
    ("蓄速", "蓄力速度增加"),
    ("蓄伤", "蓄力伤害增加"),
    ("命中", "命中率增加"),
    ("防御", "防御力增加")
]

# 从本地获取所有用户（或指定用户）
@st.cache_data(ttl=60)
def load_all_data():
    config = load_priority_config()
    default_priorities = config.get("default", ["优越代码伤害增加", "攻击力增加", "暴击伤害增加", "暴击率增加"])
    
    with equip_db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT user_id, char_name FROM character_equips")
        records = cursor.fetchall()

    rows = []
    for user_id, char_name in records:
        stats = equip_db_manager.get_character_stats(user_id, char_name)
        all_equips = equip_db_manager.get_character_all_equips(user_id, char_name)
        if not stats:
            stats = calculate_character_stats(all_equips)
            equip_db_manager.update_character_stats(user_id, char_name, stats)

        # 统计有效词条分布
        char_priorities = config.get(char_name, default_priorities)[:4]
        counts = {p: 0 for p in char_priorities}
        for eq in all_equips:
            eq_has = set()
            for eff in eq.get("effects", []):
                raw_n = eff.get("name", "").strip()
                val_s = eff.get("value", "").strip()
                std_n = eff.get("std_name") or normalize_name(raw_n)
                if std_n and "未获得" not in std_n and val_s:
                    eq_has.add(std_n)
            for std_n in eq_has:
                if std_n in counts:
                    counts[std_n] += 1

        summary_list = [f"{counts[p]}{SHORT_NAME_MAP.get(p, p[:2])}" for p in char_priorities if counts[p] > 0]
        summary_str = "、".join(summary_list) if summary_list else "无"

        total_tier = sum(v.get("total_tier", 0) for v in stats.values())
        meta = get_character_meta(char_name)
        elem = meta.get("element", "未知")

        row = {
            "用户ID": str(user_id),
            "角色": char_name,
            "属性": elem,
            "总阶数": round(total_tier, 1),
            "有效分布": summary_str
        }
        for short_n, full_n in COLUMNS:
            v = stats.get(full_n, {}).get("total_num", 0.0)
            row[short_n] = f"{v:.2f}%" if v > 0 else ""
        rows.append(row)

    df = pd.DataFrame(rows)
    if not df.empty:
        df["_order"] = df["属性"].map(lambda x: ELEMENT_ORDER.get(x, 99))
        df = df.sort_values(by=["_order", "总阶数"], ascending=[True, False]).drop(columns=["_order"])
    return df

df = load_all_data()

# 侧边栏筛选控件
if not df.empty:
    st.sidebar.header("🔍 筛选面板")
    all_users = list(df["用户ID"].unique())
    selected_user = st.sidebar.selectbox("选择指挥官账号", all_users)
    
    all_elements = ["全部"] + list(df["属性"].unique())
    selected_element = st.sidebar.selectbox("筛选属性", all_elements)

    # 过滤数据
    filtered_df = df[df["用户ID"] == selected_user]
    if selected_element != "全部":
        filtered_df = filtered_df[filtered_df["属性"] == selected_element]

    # 按属性给每行上色
    def highlight_rows(row):
        color = ELEMENT_COLORS.get(row["属性"], "")
        return [color] * len(row)

    styled_df = filtered_df.style.apply(highlight_rows, axis=1)

    st.subheader(f"指挥官 [{selected_user}] 的角色装备词条")
    st.dataframe(styled_df, use_container_width=True, height=600)
else:
    st.info("数据库中暂无词条记录，请先通过 Bot 录入！")