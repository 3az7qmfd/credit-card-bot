# core_logic.py
from datetime import datetime, timedelta, date
from typing import Dict, Any, Tuple

def safe_create_date(year, month, day):
    """为了处理 29, 30, 31 日在某些月份不存在的情况，使用安全的日期创建方法"""
    try:
        return date(year, month, day)
    except ValueError:
        # 如果日期无效（如2月30日），则取该月的最后一天
        last_day_of_month = (date(year, month, 1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        return last_day_of_month

def get_statement_date_for_purchase(today: date, statement_day: int, is_inclusive: bool) -> date:
    """计算今天的消费应该归属到哪一天的账单上"""
    # 场景1：今天就是账单日
    if today.day == statement_day:
        if is_inclusive:
            return today
        else:
            next_month_date = today.replace(day=1) + timedelta(days=32)
            return safe_create_date(next_month_date.year, next_month_date.month, statement_day)
    # 场景2：今天在账单日之前
    elif today.day < statement_day:
        return safe_create_date(today.year, today.month, statement_day)
    # 场景3：今天在账单日之后
    else: # today.day > statement_day
        next_month_date = today.replace(day=1) + timedelta(days=32)
        return safe_create_date(next_month_date.year, next_month_date.month, statement_day)

def get_due_date_from_statement(statement_date: date, due_type: str, due_value: int) -> date:
    """根据账单日计算还款日"""
    if due_type == 'fixed_day':
        due_month = statement_date.month % 12 + 1
        due_year = statement_date.year + (1 if statement_date.month == 12 else 0)
        return safe_create_date(due_year, due_month, due_value)
    elif due_type == 'days_after':
        return statement_date + timedelta(days=due_value)
    else:
        raise ValueError(f"未知的还款日类型: {due_type}")

def get_interest_free_period(card_info: Dict[str, Any], today: date = None) -> Tuple[int, date]:
    """计算从今天消费起，免息期天数和对应的最终还款日"""
    if today is None:
        today = datetime.now().date()
    
    purchase_statement_date = get_statement_date_for_purchase(
        today, card_info['statement_day'], card_info['statement_day_inclusive']
    )
    final_due_date = get_due_date_from_statement(
        purchase_statement_date, card_info['due_date_type'], card_info['due_date_value']
    )
    interest_free_days = (final_due_date - today).days
    return interest_free_days, final_due_date

def get_next_due_date(card_info: Dict[str, Any], today: date = None) -> date:
    """计算下一个即将到来的还款日"""
    if today is None:
        today = datetime.now().date()

    last_stmt_date = None
    if today.day > card_info['statement_day']:
        last_stmt_date = safe_create_date(today.year, today.month, card_info['statement_day'])
    else:
        prev_month_date = today.replace(day=1) - timedelta(days=1)
        last_stmt_date = safe_create_date(prev_month_date.year, prev_month_date.month, card_info['statement_day'])

    this_cycle_due_date = get_due_date_from_statement(last_stmt_date, card_info['due_date_type'], card_info['due_date_value'])

    if this_cycle_due_date >= today:
        return this_cycle_due_date
    else:
        next_stmt_date = get_statement_date_for_purchase(today, card_info['statement_day'], card_info['statement_day_inclusive'])
        return get_due_date_from_statement(next_stmt_date, card_info['due_date_type'], card_info['due_date_value'])

# --- 新增辅助函数 ---
def get_next_calendar_statement_date(today: date, statement_day: int) -> date:
    """
    【新增】专门用于UI展示，计算下一个日历上的账单日是哪天。
    """
    # 如果今天在账单日之前或当天
    if today.day <= statement_day:
        return safe_create_date(today.year, today.month, statement_day)
    # 如果今天已经过了本月的账单日
    else:
        next_month_date = today.replace(day=1) + timedelta(days=32)
        return safe_create_date(next_month_date.year, next_month_date.month, statement_day)