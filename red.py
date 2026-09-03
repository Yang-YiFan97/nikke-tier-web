import sqlite3
import re
import math
import io
import base64
from PIL import Image, ImageDraw, ImageFont

STAGE_DB = "stage.db"
PROD_DB = "production.db"

def get_boss_stage_info(chapter_num: int):
    """查找指定章节的 BOSS 关卡及其全局序号"""
    conn = sqlite3.connect(STAGE_DB)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT global_index, stage_name 
        FROM stage_info 
        WHERE chapter = ? AND stage_name LIKE '%BOSS%'
        ORDER BY stage_num DESC LIMIT 1
    ''', (chapter_num,))
    row = cursor.fetchone()
    
    if not row:
        cursor.execute('''
            SELECT global_index, stage_name 
            FROM stage_info 
            WHERE chapter = ? 
            ORDER BY stage_num DESC LIMIT 1
        ''', (chapter_num,))
        row = cursor.fetchone()
        
    conn.close()
    return row  # (global_index, stage_name)

def get_dust_rate_by_level(level: int) -> float:
    """从 production.db 根据基地等级获取红球速率"""
    conn = sqlite3.connect(PROD_DB)
    cursor = conn.cursor()
    cursor.execute('SELECT dust_rate FROM base_production WHERE level = ?', (level,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0.0

def get_stage_by_index(global_index: int):
    """根据全局序号反查关卡信息"""
    if global_index <= 0:
        return None
    conn = sqlite3.connect(STAGE_DB)
    cursor = conn.cursor()
    cursor.execute('SELECT chapter, stage_name FROM stage_info WHERE global_index = ?', (global_index,))
    row = cursor.fetchone()
    conn.close()
    return row  # (chapter, stage_name)

def generate_chapter_nodes(chapter_num: int):
    """严格按照 Excel 逻辑提取前置节点，并追加当前章的 BOSS 关卡为最后一行"""
    boss_info = get_boss_stage_info(chapter_num)
    if not boss_info:
        return None
    
    boss_global_idx, boss_name = boss_info
    
    # 修正公式：数据库序号不含表头，普引 = boss_global_idx - 16
    pu_yin = boss_global_idx - 16
    boss_level = 1 + math.floor((2 * pu_yin + 16) / 5)
    boss_dust = get_dust_rate_by_level(boss_level)
    
    boss_node = {
        "stage_name": boss_name,
        "target_level": boss_level,
        "actual_dust": boss_dust
    }

    # 提取红球整数部分改变的节点
    conn = sqlite3.connect(PROD_DB)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p1.level, p1.dust_rate 
        FROM base_production p1
        LEFT JOIN base_production p2 ON p1.level = p2.level + 1
        WHERE p2.level IS NULL OR CAST(p1.dust_rate AS INT) > CAST(p2.dust_rate AS INT)
        ORDER BY p1.level ASC
    ''')
    prod_milestones = cursor.fetchall()
    conn.close()

    pre_nodes = []
    seen_stages = set()

    for L, dust in prod_milestones:
        target_idx = 5 * (L - 1) - pu_yin
        
        if target_idx <= 0:
            continue
            
        stage_data = get_stage_by_index(target_idx)
        if not stage_data:
            continue
            
        ch, s_name = stage_data
        
        if ch <= chapter_num and target_idx < boss_global_idx:
            if s_name not in seen_stages:
                calc_lvl = 1 + math.floor((pu_yin + target_idx) / 5)
                calc_dust = get_dust_rate_by_level(calc_lvl)
                
                seen_stages.add(s_name)
                pre_nodes.append({
                    "stage_name": s_name,
                    "target_level": calc_lvl,
                    "actual_dust": calc_dust
                })

    if len(pre_nodes) > 14:
        pre_nodes = pre_nodes[-14:]
        
    pre_nodes.append(boss_node)
    return pre_nodes

def render_image(chapter_num: int, collected_nodes: list) -> str:
    """将节点数据绘制为图片，全黑字、白底排版"""
    width = 540
    padding_x = 35
    padding_top = 35
    title_gap = 50
    row_height = 42
    
    total_rows = len(collected_nodes) + 1
    height = padding_top + title_gap + total_rows * row_height + 30
    
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    
    font_path_candidates = ["msyh.ttc", "msyhbd.ttc", "simhei.ttf", "arial.ttf"]
    title_font = header_font = body_font = None
    
    for font_path in font_path_candidates:
        try:
            title_font = ImageFont.truetype(font_path, 22)
            header_font = ImageFont.truetype(font_path, 22)
            body_font = ImageFont.truetype(font_path, 22)
            break
        except Exception:
            continue
            
    if not title_font:
        title_font = header_font = body_font = ImageFont.load_default()

    # 1. 绘制大标题
    title_text = f"国服通关普通{chapter_num}章不漏小怪的情况下"
    draw.text((padding_x, padding_top), title_text, fill="black", font=title_font)
    
    # 2. 绘制表头
    y = padding_top + title_gap
    col1_x = padding_x
    col2_x = 260
    col3_x = 420
    
    draw.text((col1_x, y), "困难战役", fill="black", font=header_font)
    draw.text((col2_x, y), "基地等级", fill="black", font=header_font)
    draw.text((col3_x, y), "芯尘", fill="black", font=header_font)
    
    # 3. 绘制数据行
    y += row_height
    for node in collected_nodes:
        stage_str = str(node['stage_name'])
        lvl_str = f"Lv.{node['target_level']}"
        
        actual_dust = node['actual_dust']
        if actual_dust == int(actual_dust):
            dust_str = str(int(actual_dust))
        else:
            dust_str = f"{actual_dust:.2f}".rstrip('0').rstrip('.')
            
        draw.text((col1_x, y), stage_str, fill="black", font=body_font)
        draw.text((col2_x, y), lvl_str, fill="black", font=body_font)
        draw.text((col3_x, y), dust_str, fill="black", font=body_font)
        
        y += row_height

    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return f"[CQ:image,file=base64://{img_b64}]"

def generate_chapter_report(chapter_num: int) -> str:
    nodes = generate_chapter_nodes(chapter_num)
    if not nodes:
        return f"⚠️ 未在数据库中检索到第 {chapter_num} 章的关卡数据。"
    
    return render_image(chapter_num, nodes)

async def handle_red_query(user_id, raw_msg, reply_func):
    match = re.search(r"#(\d+)章红球表?", raw_msg)
    if not match:
        await reply_func("⚠️ 指令格式不正确，示例：#38章红球 或 #38章红球表")
        return
    
    chapter_num = int(match.group(1))
    report_cq = generate_chapter_report(chapter_num)
    await reply_func(report_cq)