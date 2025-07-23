# Apple-style Configuration Management
from typing import Dict, Any
from dataclasses import dataclass

@dataclass
class UIConfig:
    """Apple原则：UI配置集中管理"""
    max_input_length: int = 50
    max_cards_display: int = 10
    default_reminder_days: list = None
    
    def __post_init__(self):
        if self.default_reminder_days is None:
            self.default_reminder_days = [60, 30, 15, 7, 3, 1]

@dataclass
class ValidationConfig:
    """Apple原则：验证规则配置化"""
    min_statement_day: int = 1
    max_statement_day: int = 28
    min_due_date_value: int = 1
    max_due_date_value_fixed: int = 28
    max_due_date_value_after: int = 60
    max_annual_fee: int = 100000

@dataclass
class MessageConfig:
    """Apple原则：消息模板配置化"""
    step_indicator_format: str = "步骤 {current}/{total}: {title}"
    progress_bar_length: int = 20
    max_alternatives_shown: int = 2

class AppConfig:
    """Apple原则：应用配置统一管理"""
    
    def __init__(self):
        self.ui = UIConfig()
        self.validation = ValidationConfig()
        self.messages = MessageConfig()
    
    @property
    def currency_types(self) -> Dict[str, str]:
        """Apple原则：常量配置化"""
        return {
            "local": "人民币",
            "foreign": "外币", 
            "all": "全币种"
        }
    
    @property
    def editable_fields(self) -> Dict[str, str]:
        """Apple原则：可编辑字段配置化"""
        return {
            'nickname': '别名',
            'last_four_digits': '后四位',
            'bank_name': '银行',
            'statement_day': '账单日',
            'statement_day_inclusive': '账单日规则',
            'due_date_rule': '还款规则',
            'currency_type': '币种支持',
            'annual_fee': '年费信息'
        }
    
    @staticmethod
    def get_event_status_emoji(days_diff: int) -> str:
        """Apple原则：统一的状态图标系统"""
        if days_diff < 0:
            return "✅"  # 已过期
        elif days_diff == 0:
            return "🔴"  # 今日还款
        elif days_diff <= 3:
            return "🟡"  # 近期还款
        else:
            return "🟢"  # 未来还款
    
    @staticmethod
    def get_event_status_text(days_diff: int) -> str:
        """Apple原则：统一的状态文本系统"""
        if days_diff < 0:
            return f"已过去 {abs(days_diff)} 天"
        elif days_diff == 0:
            return "今天"
        elif days_diff <= 3:
            return f"{days_diff} 天后"
        else:
            return f"{days_diff} 天后"
    
    @property
    def calendar_legend(self) -> str:
        """Apple原则：日历图例配置化"""
        return (
            "📖 <b>图例说明</b>\n"
            "🔴 今日还款  🟡 近期还款  🟢 未来还款  ✅ 已过期"
        )

# Global configuration instance
config = AppConfig()