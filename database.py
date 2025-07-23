# database.py
import sqlite3
from pathlib import Path
import logging
from typing import List, Dict, Any, Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

DATA_DIR = Path(__file__).parent / "data"
DATABASE_FILE = DATA_DIR / "cards.db"

def get_connection():
    return sqlite3.connect(DATABASE_FILE)

def init_db():
    logging.info("正在初始化数据库...")
    try:
        DATA_DIR.mkdir(exist_ok=True)
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nickname TEXT NOT NULL UNIQUE,
                last_four_digits TEXT,
                bank_name TEXT,
                statement_day INTEGER NOT NULL,
                statement_day_inclusive BOOLEAN NOT NULL,
                due_date_type TEXT NOT NULL CHECK(due_date_type IN ('fixed_day', 'days_after')),
                due_date_value INTEGER NOT NULL,
                currency_type TEXT NOT NULL,
                annual_fee_amount INTEGER DEFAULT 0,
                annual_fee_date TEXT,
                has_waiver BOOLEAN DEFAULT FALSE,
                is_waived_for_cycle BOOLEAN DEFAULT FALSE,
                waiver_reset_date DATE
            )
            """)
            conn.commit()
            logging.info("数据库初始化成功。")
    except Exception as e:
        logging.error(f"数据库初始化失败: {e}")
        raise

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def add_card(card_data: Dict[str, Any]) -> bool:
    fields = [
        'nickname', 'last_four_digits', 'bank_name', 'statement_day',
        'statement_day_inclusive', 'due_date_type', 'due_date_value',
        'currency_type', 'annual_fee_amount', 'annual_fee_date',
        'has_waiver', 'is_waived_for_cycle', 'waiver_reset_date'
    ]
    sql = f"INSERT INTO cards ({', '.join(fields)}) VALUES ({', '.join(['?'] * len(fields))})"
    values = tuple(card_data.get(field) for field in fields)
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, values)
            conn.commit()
            logging.info(f"成功添加卡片: {card_data.get('nickname')}")
            return True
    except sqlite3.IntegrityError:
        logging.error(f"添加卡片失败: 别名 '{card_data.get('nickname')}' 已存在。")
        return False
    except Exception as e:
        logging.error(f"添加卡片时发生未知错误: {e}")
        return False

def get_all_cards() -> List[Dict[str, Any]]:
    try:
        with get_connection() as conn:
            conn.row_factory = dict_factory
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM cards ORDER BY nickname")
            return cursor.fetchall()
    except Exception as e:
        logging.error(f"获取所有卡片时出错: {e}")
        return []

def get_card_by_nickname(nickname: str) -> Optional[Dict[str, Any]]:
    try:
        with get_connection() as conn:
            conn.row_factory = dict_factory
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM cards WHERE nickname = ?", (nickname,))
            return cursor.fetchone()
    except Exception as e:
        logging.error(f"通过别名获取卡片时出错: {e}")
        return None

def delete_card(nickname: str) -> bool:
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM cards WHERE nickname = ?", (nickname,))
            conn.commit()
            if cursor.rowcount > 0:
                logging.info(f"成功删除卡片: {nickname}")
                return True
            return False
    except Exception as e:
        logging.error(f"删除卡片时出错: {e}")
        return False

def update_card(nickname: str, updates: Dict[str, Any]) -> bool:
    """
    【已重构】更新指定卡片的多个字段。
    updates 是一个包含 {字段: 新值} 的字典。
    """
    if not updates:
        return False

    # 构造 SQL 的 SET 部分
    set_clause = ", ".join([f"{field} = ?" for field in updates.keys()])
    values = list(updates.values())
    values.append(nickname) # 用于 WHERE 子句

    sql = f"UPDATE cards SET {set_clause} WHERE nickname = ?"
    
    # 验证字段名，防止SQL注入
    allowed_fields = [
        'nickname', 'last_four_digits', 'bank_name', 'statement_day',
        'statement_day_inclusive', 'due_date_type', 'due_date_value',
        'currency_type', 'annual_fee_amount', 'annual_fee_date', 'has_waiver',
        'is_waived_for_cycle', 'waiver_reset_date'
    ]
    for field in updates.keys():
        if field not in allowed_fields:
            logging.error(f"尝试更新一个不允许的字段: {field}")
            return False

    # 添加重试逻辑处理数据库锁定
    max_retries = 3
    for attempt in range(max_retries):
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, tuple(values))
                conn.commit()
                if cursor.rowcount > 0:
                    logging.info(f"成功更新卡片 {nickname} 的数据。")
                    return True
                else:
                    logging.warning(f"未找到要更新的卡片: {nickname}")
                    return False
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                logging.warning(f"数据库锁定，重试 {attempt + 1}/{max_retries}")
                import time
                time.sleep(0.1 * (attempt + 1))  # 递增延迟
                continue
            else:
                logging.error(f"数据库操作错误: {e}")
                return False
        except Exception as e:
            logging.error(f"更新卡片 {nickname} 时出错: {e}")
            return False
    
    return False
