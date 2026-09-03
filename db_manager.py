import sqlite3
import json
import os

# ----------------------------------------------------------------------
# 路径定义 (彻底脱离 config.py)
# ----------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

# 1. 默认/桌面端数据库路径
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "character_cards.db")

# 2. 专属于 #词条 和 #词条导入 命令使用的数据库路径
EQUIP_DB_PATH = os.path.join(ASSETS_DIR, "装备词条.db")


class DBManager:
    def __init__(self, db_path):
        self.db_path = db_path
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # 装备详情表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS character_equips (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    char_name TEXT,
                    equip_name TEXT,
                    effects_json TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, char_name, equip_name)
                )
            """)
            # 新增：角色汇总属性统计表（记录 0 阶与总和）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS character_stats (
                    user_id TEXT,
                    char_name TEXT,
                    stats_json TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, char_name)
                )
            """)
            conn.commit()

    def save_equip_data(self, user_id, char_name, equip_name, effects):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO character_equips (user_id, char_name, equip_name, effects_json, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, char_name, equip_name) DO UPDATE SET
                    effects_json = excluded.effects_json,
                    updated_at = CURRENT_TIMESTAMP
            """, (str(user_id), char_name, equip_name, json.dumps(effects, ensure_ascii=False)))
            conn.commit()

    def get_character_all_equips(self, user_id, char_name):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # 【修复】：改为精确匹配 = ?
            cursor.execute("""
                SELECT equip_name, effects_json 
                FROM character_equips 
                WHERE user_id = ? AND char_name = ? 
                ORDER BY id ASC
            """, (str(user_id), char_name))
            rows = cursor.fetchall()
            return [{"equip_name": r[0], "effects": json.loads(r[1]) if r[1] else []} for r in rows]

    def update_character_stats(self, user_id, char_name, stats_dict):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO character_stats (user_id, char_name, stats_json, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, char_name) DO UPDATE SET
                    stats_json = excluded.stats_json,
                    updated_at = CURRENT_TIMESTAMP
            """, (str(user_id), char_name, json.dumps(stats_dict, ensure_ascii=False)))
            conn.commit()

    def get_character_stats(self, user_id, char_name):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # 【修复】：改为精确匹配 = ?
            cursor.execute("""
                SELECT stats_json 
                FROM character_stats 
                WHERE user_id = ? AND char_name = ?
            """, (str(user_id), char_name))
            row = cursor.fetchone()
            if row and row[0]:
                return json.loads(row[0])
            return None


# 1. 通用/默认数据库实例
db_manager = DBManager(DEFAULT_DB_PATH)

# 2. 专供 #词条 和 #词条导入 使用的专属数据库实例 (assets/装备词条.db)
equip_db_manager = DBManager(EQUIP_DB_PATH)