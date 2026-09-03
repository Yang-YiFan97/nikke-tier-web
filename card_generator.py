import os
import io
import json
import re
import difflib
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter

# ----------------------------------------------------------------------
# 0. 基础路径配置
# ----------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

CHARACTER_IMG_DIR = os.path.join(ASSETS_DIR, "character")
HEAD_IMG_DIR = os.path.join(ASSETS_DIR, "character_head")
PROPERTY_IMG_DIR = os.path.join(ASSETS_DIR, "character_property")
WEAPON_IMG_DIR = os.path.join(ASSETS_DIR, "character_weapon")
CHARACTER_LIST_PATH = os.path.join(ASSETS_DIR, "character_list.json")

# ----------------------------------------------------------------------
# 1. 简称字典与 15 阶数值映射表
# ----------------------------------------------------------------------
SHORT_NAME_MAP = {
    "优越代码伤害增加": "优越",
    "攻击力增加": "攻击",
    "暴击伤害增加": "暴伤",
    "暴击率增加": "暴击",
    "最大装弹数增加": "弹容",
    "蓄力伤害增加": "蓄伤",
    "蓄力速度增加": "蓄速",
    "命中率增加": "命中",
    "防御力增加": "防御"
}

TIER_MAP = {
    "优越代码伤害增加": {
        "9.54": 1, "10.94": 2, "12.34": 3, "13.75": 4, "15.15": 5,
        "16.55": 6, "17.95": 7, "19.35": 8, "20.75": 9, "22.15": 10,
        "23.56": 11, "24.96": 12, "26.36": 13, "27.76": 14, "29.16": 15
    },
    "攻击力增加": {
        "4.77": 1, "5.47": 2, "6.18": 3, "6.88": 4, "7.59": 5,
        "8.29": 6, "9.00": 7, "9.70": 8, "10.40": 9, "11.11": 10,
        "11.81": 11, "12.52": 12, "13.22": 13, "13.93": 14, "14.63": 15
    },
    "最大装弹数增加": {
        "27.84": 1, "31.95": 2, "36.06": 3, "40.17": 4, "44.28": 5,
        "48.39": 6, "52.50": 7, "56.60": 8, "60.71": 9, "64.82": 10,
        "68.93": 11, "73.04": 12, "77.50": 13, "81.26": 14, "85.37": 15
    },
    "蓄力速度增加": {
        "1.98": 1, "2.28": 2, "2.57": 3, "2.86": 4, "3.16": 5,
        "3.45": 6, "3.75": 7, "4.04": 8, "4.33": 9, "4.63": 10,
        "4.92": 11, "5.21": 12, "5.51": 13, "5.80": 14, "6.09": 15
    },
    "蓄力伤害增加": {
        "4.77": 1, "5.47": 2, "6.18": 3, "6.88": 4, "7.59": 5,
        "8.29": 6, "9.00": 7, "9.70": 8, "10.40": 9, "11.11": 10,
        "11.81": 11, "12.52": 12, "13.22": 13, "13.93": 14, "14.63": 15
    },
    "暴击率增加": {
        "2.30": 1, "2.64": 2, "2.98": 3, "3.32": 4, "3.66": 5,
        "4.00": 6, "4.35": 7, "4.69": 8, "5.03": 9, "5.37": 10,
        "5.71": 11, "6.05": 12, "6.39": 13, "6.73": 14, "7.07": 15
    },
    "暴击伤害增加": {
        "6.64": 1, "7.62": 2, "8.60": 3, "9.58": 4, "10.56": 5,
        "11.54": 6, "12.52": 7, "13.50": 8, "14.48": 9, "15.46": 10,
        "16.44": 11, "17.42": 12, "18.40": 13, "19.38": 14, "20.36": 15
    },
    "命中率增加": {
        "4.77": 1, "5.47": 2, "6.18": 3, "6.88": 4, "7.59": 5,
        "8.29": 6, "9.00": 7, "9.70": 8, "10.40": 9, "11.11": 10,
        "11.81": 11, "12.52": 12, "13.22": 13, "13.93": 14, "14.63": 15
    },
    "防御力增加": {
        "4.77": 1, "5.47": 2, "6.18": 3, "6.88": 4, "7.59": 5,
        "8.29": 6, "9.00": 7, "9.70": 8, "10.40": 9, "11.11": 10,
        "11.81": 11, "12.52": 12, "13.22": 13, "13.93": 14, "14.63": 15
    }
}

def normalize_equip_name(raw_name: str) -> str:
    if not raw_name:
        return "未知装备"
    name = raw_name.strip()
    if any(k in name for k in ["面罩", "护目镜", "头盔", "头部"]): return "v金属面罩"
    elif any(k in name for k in ["背心", "夹克", "防护服", "身体", "胸甲", "胸"]): return "v金属背心"
    elif any(k in name for k in ["护臂", "手套", "臂铠", "手部", "臂"]): return "v金属护臂"
    elif any(k in name for k in ["靴子", "靴", "鞋", "护腿", "脚部", "腿"]): return "v金属靴子"
    return name

def normalize_name(raw_name):
    if not raw_name or "未获得" in raw_name:
        return ""
        
    clean = raw_name.replace("【", "").replace("】", "").replace("[", "").replace("]", "").strip()
    
    # 1. 尝试直接精确匹配
    if clean in SHORT_NAME_MAP:
        return clean
        
    # 2. 尝试子串包含匹配
    for std_name in SHORT_NAME_MAP.keys():
        core_std = std_name.replace("增加", "")
        core_clean = clean.replace("增加", "")
        if core_std in core_clean or core_clean in core_std:
            return std_name
            
    # 3. 相似度模糊匹配（应对 OCR 错字漏字）
    best_match = None
    highest_ratio = 0.0
    for std_name in SHORT_NAME_MAP.keys():
        # 计算当前识别文本与各个官方词条的相似度
        ratio = difflib.SequenceMatcher(None, clean, std_name).ratio()
        if ratio > highest_ratio:
            highest_ratio = ratio
            best_match = std_name
            
    # 如果最高相似度大于 0.4（说明至少有一半的字是对上的），就强行修正为该官方词条
    if highest_ratio > 0.4 and best_match:
        return best_match
        
    return clean

def load_priority_config():
    config_path = os.path.join(ASSETS_DIR, "priority_config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception: pass
    return {
        "default": ["优越代码伤害增加", "攻击力增加", "暴击伤害增加", "暴击率增加"]
    }

def get_character_meta(official_name: str) -> dict:
    if os.path.exists(CHARACTER_LIST_PATH):
        try:
            with open(CHARACTER_LIST_PATH, "r", encoding="utf-8") as f:
                c_dict = json.load(f)
                return c_dict.get(official_name, {})
        except Exception as e: print(f"⚠️ [JSON读取异常]: {e}")
    return {}

def load_character_centered_bg(official_name: str, target_size: tuple[int, int]) -> Image.Image:
    card_w, card_h = target_size
    possible_paths = [
        os.path.join(CHARACTER_IMG_DIR, f"{official_name}.png"),
        os.path.join(CHARACTER_IMG_DIR, f"{official_name}.jpg"),
        os.path.join(ASSETS_DIR, f"char_{official_name}.png"),
    ]
    for p in possible_paths:
        if os.path.exists(p):
            try:
                raw_img = Image.open(p).convert("RGBA")
                return ImageOps.fit(raw_img, (card_w, card_h), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
            except Exception: pass
    return Image.new("RGBA", (card_w, card_h), (210, 225, 245, 255))

def load_icon(path: str, target_size: tuple[int, int], is_rounded: bool = False, radius: int = 12) -> Image.Image | None:
    if os.path.exists(path):
        try:
            raw_img = Image.open(path).convert("RGBA")
            fitted = ImageOps.fit(raw_img, target_size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
            if is_rounded:
                mask = Image.new("L", target_size, 0)
                ImageDraw.Draw(mask).rounded_rectangle([0, 0, target_size[0] - 1, target_size[1] - 1], radius=radius, fill=255)
                output = Image.new("RGBA", target_size, (0, 0, 0, 0))
                output.paste(fitted, (0, 0), mask)
                return output
            return fitted
        except Exception: pass
    return None

def get_tier_from_map(tier_map, name, val_str):
    if not name or "未获得" in name or not val_str:
        return 0
    try:
        val_matches = re.findall(r"[\d\.]+", val_str)
        if not val_matches: return 0
        val_num = float(val_matches[0])
    except Exception: return 0

    clean_name = normalize_name(name)
    if clean_name not in tier_map: return 1

    mapping = tier_map[clean_name]
    best_tier = 1
    min_diff = float('inf')
    for ref_val_str, t_level in mapping.items():
        try: ref_val = float(ref_val_str)
        except ValueError: continue
        diff = abs(ref_val - val_num)
        if diff < min_diff:
            min_diff = diff
            best_tier = t_level
    return best_tier

# ==============================================================================
# 核心属性统计函数 (供存储前/读取后调用)
# ==============================================================================
def calculate_character_stats(equips_data):
    """
    计算所有装备中每个词条的汇总数值与汇总阶数。
    默认给 9 个标准词条全部分配 0，保证数据库有 0 的记录。
    """
    summary_dict = {}
    for std_name in SHORT_NAME_MAP.keys():
        summary_dict[std_name] = {"total_tier": 0, "total_num": 0.0, "unit": "%"}

    for eq in equips_data:
        for eff in eq.get("effects", []):
            raw_n = eff.get("name", "").strip()
            val_s = eff.get("value", "").strip()
            std_n = eff.get("std_name") or normalize_name(raw_n)

            if std_n and "未获得" not in std_n and val_s:
                # 优先读取字典里存好的单件 tier
                t_val = eff.get("tier")
                if t_val is None:
                    t_val = get_tier_from_map(TIER_MAP, std_n, val_s)
                try:
                    num_val = float(re.findall(r"[\d\.]+", val_s)[0])
                except Exception:
                    num_val = 0.0

                if std_n in summary_dict:
                    summary_dict[std_n]["total_tier"] += t_val
                    summary_dict[std_n]["total_num"] += num_val
    return summary_dict

def draw_blur_only_panel(canvas, rect, radius=12, blur_radius=8, outline_color=(255, 255, 255, 150), overlay_alpha=15):
    x, y, w, h = rect
    card_w, card_h = canvas.size

    margin = blur_radius
    crop_x1 = max(0, x - margin)
    crop_y1 = max(0, y - margin)
    crop_x2 = min(card_w, x + w + margin)
    crop_y2 = min(card_h, y + h + margin)

    bg_patch = canvas.crop((crop_x1, crop_y1, crop_x2, crop_y2))
    blurred_patch = bg_patch.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    
    paste_x = x - crop_x1
    paste_y = y - crop_y1
    actual_patch = blurred_patch.crop((paste_x, paste_y, paste_x + w, paste_y + h)).convert("RGBA")

    if overlay_alpha > 0:
        white_overlay = Image.new("RGBA", (w, h), (255, 255, 255, overlay_alpha))
        actual_patch = Image.alpha_composite(actual_patch, white_overlay)

    canvas.paste(actual_patch, (x, y), actual_patch)

    outline_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    o_draw = ImageDraw.Draw(outline_img)
    o_draw.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, outline=outline_color, width=max(1, int(canvas.size[0]/500)))
    canvas.paste(outline_img, (x, y), outline_img)

def generate_equip_card_image(char_name, equips_data, stats_data=None):
    tier_map = TIER_MAP
    scale = 3.2
    card_w = int(500 * scale)
    card_h = int(750 * scale)

    if not stats_data:
        stats_data = calculate_character_stats(equips_data)

    meta = get_character_meta(char_name)
    config = load_priority_config()
    if char_name in config:
        char_priorities = config[char_name][:4]
    else:
        default_list = config.get("default", [
            "优越代码伤害增加", "攻击力增加", "暴击伤害增加", "暴击率增加"
        ])
        char_priorities = default_list[:4]

    canvas = Image.new("RGBA", (card_w, card_h))
    bg = load_character_centered_bg(char_name, (card_w, card_h))
    canvas.paste(bg, (0, 0))

    try:
        font_title = ImageFont.truetype("msyhbd.ttc", int(22 * scale))
        font_burst_tag = ImageFont.truetype("msyhbd.ttc", int(14 * scale))
        font_class_comp = ImageFont.truetype("msyhbd.ttc", int(13 * scale))
        font_big = ImageFont.truetype("msyhbd.ttc", int(16 * scale))
        font_mid = ImageFont.truetype("msyhbd.ttc", int(13 * scale))
        font_small = ImageFont.truetype("msyh.ttc", int(11 * scale))
        font_small_bold = ImageFont.truetype("msyhbd.ttc", int(11 * scale))
    except IOError:
        font_title = font_burst_tag = font_class_comp = font_big = font_mid = font_small = font_small_bold = ImageFont.load_default()

    # 计算总阶数和有效阶数
    total_tier_sum = sum(v.get("total_tier", 0) for v in stats_data.values())
    effective_tier_sum = sum(stats_data.get(name, {}).get("total_tier", 0) for name in char_priorities)

    # ------------------------------------------------------------------
    # 调整左上角模块 (删掉头像，上移内容，减小高度)
    # ------------------------------------------------------------------
    left_x, left_y = int(20 * scale), int(20 * scale)
    left_w, left_h = int(185 * scale), int(135 * scale)

    draw_blur_only_panel(
        canvas,
        (left_x, left_y, left_w, left_h),
        radius=int(18 * scale),
        blur_radius=int(6 * scale),
        outline_color=(255, 255, 255, 150),
        overlay_alpha=200
    )

    t_draw = ImageDraw.Draw(canvas)
    name_y = left_y + int(24 * scale)
    name_bbox = font_title.getbbox(char_name)
    name_w = name_bbox[2] - name_bbox[0]
    t_draw.text((left_x + (left_w - name_w) // 2, name_y), char_name, fill="#111111", font=font_title)

    element_name = meta.get("element", "")
    weapon_name = meta.get("weapon", "")
    burst_name = meta.get("burst", "III")

    row_icon_y = left_y + int(60 * scale)
    icon_sz = int(28 * scale)
    burst_w, burst_h = int(32 * scale), icon_sz
    total_w = icon_sz + int(8 * scale) + icon_sz + int(8 * scale) + burst_w
    start_ix = left_x + (left_w - total_w) // 2

    if element_name:
        prop_path = os.path.join(PROPERTY_IMG_DIR, f"{element_name}.png")
        prop_img = load_icon(prop_path, (icon_sz, icon_sz))
        if prop_img:
            canvas.paste(prop_img, (start_ix, row_icon_y), prop_img)

    if weapon_name:
        weapon_path = os.path.join(WEAPON_IMG_DIR, f"{weapon_name}.png")
        weapon_img = load_icon(weapon_path, (icon_sz, icon_sz))
        if weapon_img:
            canvas.paste(weapon_img, (start_ix + icon_sz + int(8 * scale), row_icon_y), weapon_img)

    burst_x = start_ix + (icon_sz + int(8 * scale)) * 2
    burst_tag = Image.new("RGBA", (burst_w, burst_h), (0, 0, 0, 0))
    b_draw = ImageDraw.Draw(burst_tag)
    b_draw.rounded_rectangle([0, 0, burst_w - 1, burst_h - 1], radius=int(6 * scale), fill="#c0392b")
    b_draw.text((burst_w // 2, burst_h // 2 - int(1 * scale)), burst_name, fill="#ffffff", font=font_burst_tag, anchor="mm")
    canvas.paste(burst_tag, (burst_x, row_icon_y), burst_tag)

    class_name = meta.get("class", "火力型")
    company_name = meta.get("company", "泰特拉")
    desc_y = left_y + int(98 * scale)

    c_text = f"{class_name} · {company_name}"
    c_bbox = font_class_comp.getbbox(c_text)
    cw = c_bbox[2] - c_bbox[0]
    cx = left_x + (left_w - cw) // 2
    t_draw.text((cx, desc_y), class_name, fill="#c0392b", font=font_class_comp)
    dot_x = cx + font_class_comp.getbbox(class_name)[2]
    t_draw.text((dot_x, desc_y), " · ", fill="#aa0071", font=font_class_comp)
    comp_x = dot_x + font_class_comp.getbbox(" · ")[2]
    t_draw.text((comp_x, desc_y), company_name, fill="#aa0071", font=font_class_comp)

    # ------------------------------------------------------------------
    # 中部词条汇总直接使用 stats_data
    # ------------------------------------------------------------------
    def get_item_data(name):
        return stats_data.get(name, {"total_tier": 0, "total_num": 0.0, "unit": "%"})

    # 高度从 140 增加到 172 以容纳新的标题栏
    sum_x, sum_y, sum_w, sum_h = int(15 * scale), int(420 * scale), card_w - int(30 * scale), int(172 * scale)
    draw_blur_only_panel(
        canvas, 
        (sum_x, sum_y, sum_w, sum_h), 
        radius=int(12 * scale), 
        blur_radius=int(10 * scale), 
        outline_color=(255, 255, 255, 150),
        overlay_alpha=15
    )

    # 绘制中部模块内的标题与阶数统计
    header_y = sum_y + int(12 * scale)
    t_draw.text((sum_x + int(15 * scale), header_y), "核心词条汇总", fill="#007acc", font=font_big)

    info_str = f"总阶数: {total_tier_sum:.1f} 阶   |   有效阶数: {effective_tier_sum:.1f} 阶"
    info_bbox = font_mid.getbbox(info_str)
    info_w = info_bbox[2] - info_bbox[0]
    t_draw.text((sum_x + sum_w - info_w - int(15 * scale), header_y + int(2 * scale)), info_str, fill="#333333", font=font_mid)

    # 下移条目的起始高度
    item_bg_w = sum_w - int(20 * scale)
    item_bg_h = int(36 * scale)
    s_y = sum_y + int(42 * scale)

    if len(char_priorities) >= 1:
        name = char_priorities[0]
        d_val = get_item_data(name)
        item_bg = Image.new("RGBA", (item_bg_w, item_bg_h), (255, 255, 255, 120))
        ib_draw = ImageDraw.Draw(item_bg)
        ib_draw.text((int(15 * scale), int(8 * scale)), f"【{name}】", fill="#222222", font=font_mid)
        val_display = f"{d_val['total_num']:.2f}{d_val['unit']}"
        ib_draw.text((int(220 * scale), int(8 * scale)), val_display, fill="#111111", font=font_big)
        ib_draw.text((int(370 * scale), int(9 * scale)), f"{d_val['total_tier']}阶", fill="#333333", font=font_mid)
        canvas.paste(item_bg, (sum_x + int(10 * scale), s_y), item_bg)
        s_y += int(42 * scale)

    if len(char_priorities) >= 2:
        name = char_priorities[1]
        d_val = get_item_data(name)
        item_bg = Image.new("RGBA", (item_bg_w, item_bg_h), (255, 255, 255, 120))
        ib_draw = ImageDraw.Draw(item_bg)
        ib_draw.text((int(15 * scale), int(8 * scale)), f"【{name}】", fill="#222222", font=font_mid)
        val_display = f"{d_val['total_num']:.2f}{d_val['unit']}"
        ib_draw.text((int(220 * scale), int(8 * scale)), val_display, fill="#111111", font=font_big)
        ib_draw.text((int(370 * scale), int(9 * scale)), f"{d_val['total_tier']}阶", fill="#333333", font=font_mid)
        canvas.paste(item_bg, (sum_x + int(10 * scale), s_y), item_bg)
        s_y += int(42 * scale)

    if len(char_priorities) == 3:
        name = char_priorities[2]
        d_val = get_item_data(name)
        item_bg = Image.new("RGBA", (item_bg_w, item_bg_h), (255, 255, 255, 120))
        ib_draw = ImageDraw.Draw(item_bg)
        ib_draw.text((int(15 * scale), int(8 * scale)), f"【{name}】", fill="#222222", font=font_mid)
        val_display = f"{d_val['total_num']:.2f}{d_val['unit']}"
        ib_draw.text((int(220 * scale), int(8 * scale)), val_display, fill="#111111", font=font_big)
        ib_draw.text((int(370 * scale), int(9 * scale)), f"{d_val['total_tier']}阶", fill="#333333", font=font_mid)
        canvas.paste(item_bg, (sum_x + int(10 * scale), s_y), item_bg)
    else:
        half_w = (item_bg_w - int(6 * scale)) // 2

        left_bg = Image.new("RGBA", (half_w, item_bg_h), (255, 255, 255, 120))
        if len(char_priorities) >= 3:
            name = char_priorities[2]
            d_val = get_item_data(name)
            l_draw = ImageDraw.Draw(left_bg)
            short_n_l = SHORT_NAME_MAP.get(name, name[:2])
            l_draw.text((int(10 * scale), int(9 * scale)), f"【{short_n_l}】", fill="#222222", font=font_small_bold)
            val_display_l = f"{d_val['total_num']:.2f}{d_val['unit']}"
            l_draw.text((int(85 * scale), int(9 * scale)), val_display_l, fill="#111111", font=font_small_bold)
            l_draw.text((int(155 * scale), int(10 * scale)), f"{d_val['total_tier']}阶", fill="#333333", font=font_small)
        canvas.paste(left_bg, (sum_x + int(10 * scale), s_y), left_bg)

        right_bg = Image.new("RGBA", (half_w, item_bg_h), (255, 255, 255, 120))
        if len(char_priorities) >= 4:
            name = char_priorities[3]
            d_val = get_item_data(name)
            r_draw = ImageDraw.Draw(right_bg)
            short_n_r = SHORT_NAME_MAP.get(name, name[:2])
            r_draw.text((int(10 * scale), int(9 * scale)), f"【{short_n_r}】", fill="#222222", font=font_small_bold)
            val_display_r = f"{d_val['total_num']:.2f}{d_val['unit']}"
            r_draw.text((int(85 * scale), int(9 * scale)), val_display_r, fill="#111111", font=font_small_bold)
            r_draw.text((int(155 * scale), int(10 * scale)), f"{d_val['total_tier']}阶", fill="#333333", font=font_small)
        canvas.paste(right_bg, (sum_x + int(10 * scale) + half_w + int(6 * scale), s_y), right_bg)

    grid_w, grid_h = int(228 * scale), int(120 * scale)
    
    # 底部装备网格为了适应增加高度的中部模块，向下平移
    positions = [
        (int(15 * scale), int(605 * scale)), 
        (int(255 * scale), int(605 * scale)), 
        (int(15 * scale), int(735 * scale)), 
        (int(255 * scale), int(735 * scale))
    ]
    # 动态扩展卡片底部，防止裁边
    new_card_h = int(870 * scale)
    new_canvas = Image.new("RGBA", (card_w, new_card_h))
    new_bg = load_character_centered_bg(char_name, (card_w, new_card_h))
    new_canvas.paste(new_bg, (0, 0))
    new_canvas.paste(canvas, (0, 0))
    canvas = new_canvas
    
    slot_icon_names = ["head.png", "chest.png", "arm.png", "leg.png"]
    eq_icon_sz = int(50 * scale)

    slot_order = ["v金属面罩", "v金属背心", "v金属护臂", "v金属靴子"]
    equips_by_slot = {}
    for eq in equips_data:
        std_slot = normalize_equip_name(eq.get("equip_name", ""))
        equips_by_slot[std_slot] = eq

    for idx in range(4):
        pos_x, pos_y = positions[idx]
        draw_blur_only_panel(
            canvas, 
            (pos_x, pos_y, grid_w, grid_h), 
            radius=int(10 * scale), 
            blur_radius=int(8 * scale), 
            outline_color=(255, 255, 255, 120),
            overlay_alpha=15
        )

        eq_draw = ImageDraw.Draw(canvas)
        icon_path = os.path.join(ASSETS_DIR, slot_icon_names[idx])
        icon_img = load_icon(icon_path, (eq_icon_sz, eq_icon_sz))
        if icon_img:
            canvas.paste(icon_img, (pos_x + int(6 * scale), pos_y + int(6 * scale)), icon_img)

        std_slot_name = slot_order[idx]
        if std_slot_name in equips_by_slot:
            eq = equips_by_slot[std_slot_name]
            effects = eq.get("effects", [])

            eff_y = pos_y + int(6 * scale)
            # 严格按照 AI 返回的原始 3 个槽位顺序遍历渲染
            for i in range(3):
                if i < len(effects):
                    eff = effects[i]
                    raw_n = eff.get("name", "").strip()
                    val_s = eff.get("value", "").strip()
                    std_n = eff.get("std_name") or normalize_name(raw_n)
                    
                    t_lvl = eff.get("tier")
                    if t_lvl is None:
                        t_lvl = get_tier_from_map(tier_map, std_n, val_s)

                    if std_n and "未获得" not in std_n and val_s:
                        short_n = SHORT_NAME_MAP.get(std_n, std_n[:2])
                        
                        # ----------------------------------------------------
                        # 【新增逻辑】：处理 12 阶以上蓝字，15阶黑底蓝字联动
                        # ----------------------------------------------------
                        name_color = "#222222"
                        val_color = "#111111"
                        tier_color = "#444444"
                        
                        # >=12阶时，名称、数值、阶数全局变为亮蓝色
                        if t_lvl >= 12:
                            name_color = "#00a2ff"
                            val_color = "#00a2ff"
                            tier_color = "#00a2ff"
                            
                        val_x = pos_x + int(105 * scale)
                        
                        # 如果是 15 阶，画一个横跨整行的黑色背景条
                        if t_lvl == 15:
                            bbox = eq_draw.textbbox((val_x, eff_y), val_s, font=font_small_bold)
                            pad_y = int(2 * scale)
                            bg_left = pos_x + int(64 * scale)
                            bg_right = pos_x + grid_w - int(8 * scale)
                            eq_draw.rectangle([bg_left, bbox[1] - pad_y, bg_right, bbox[3] + pad_y], fill="#000000")
                            
                        # 写入文本，统一使用 font_small_bold
                        eq_draw.text((pos_x + int(68 * scale), eff_y), short_n, fill=name_color, font=font_small_bold)
                        eq_draw.text((val_x, eff_y), val_s, fill=val_color, font=font_small_bold)
                        eq_draw.text((pos_x + int(185 * scale), eff_y), f"{t_lvl}阶", fill=tier_color, font=font_small_bold)
                    else:
                        eq_draw.text((pos_x + int(68 * scale), eff_y), "未获得效果", fill="#a0a0a0", font=font_small)
                else:
                    eq_draw.text((pos_x + int(68 * scale), eff_y), "未获得效果", fill="#a0a0a0", font=font_small)
                eff_y += int(20 * scale)
        else:
            eff_y = pos_y + int(6 * scale)
            for i in range(3):
                eq_draw.text((pos_x + int(68 * scale), eff_y), "未获得效果", fill="#a0a0a0", font=font_small)
                eff_y += int(20 * scale)

    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, format="PNG", quality=95)
    buf.seek(0)
    return buf.getvalue()