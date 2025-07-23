# Apple-style Error Handling System
from typing import Optional, Dict, Any
import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

class AppleErrorHandler:
    """Apple-style error handling: graceful, user-friendly, and informative"""
    
    # Apple原则：错误消息模板化
    ERROR_MESSAGES = {
        'database_error': "⚠️ 数据暂时不可用\n请稍后重试",
        'card_not_found': "💳 未找到指定卡片\n使用 /portfolio 查看现有卡片",
        'invalid_input': "❌ 输入格式不正确\n请检查后重新输入",
        'permission_denied': "🔒 抱歉，这是私人机器人",
        'network_error': "🌐 网络连接异常\n请检查网络后重试",
        'unknown_error': "😅 出现了意外问题\n我们正在处理中"
    }
    
    @staticmethod
    async def handle_gracefully(
        update: Update, 
        context: ContextTypes.DEFAULT_TYPE,
        error_type: str,
        custom_message: Optional[str] = None,
        log_details: Optional[Dict[str, Any]] = None
    ):
        """Apple原则：优雅的错误处理，用户体验优先"""
        
        # Log the error for debugging
        if log_details:
            logging.error(f"Error {error_type}: {log_details}")
        
        # Get user-friendly message
        message = custom_message or AppleErrorHandler.ERROR_MESSAGES.get(
            error_type, 
            AppleErrorHandler.ERROR_MESSAGES['unknown_error']
        )
        
        # Send to user based on update type
        try:
            if update.message:
                await update.message.reply_text(message, parse_mode=ParseMode.HTML)
            elif update.callback_query:
                await update.callback_query.edit_message_text(message, parse_mode=ParseMode.HTML)
        except Exception as e:
            # Fallback: log if we can't even send error message
            logging.critical(f"Failed to send error message: {e}")
    
    @staticmethod
    def validate_card_data(card_data: Dict[str, Any]) -> tuple[bool, str]:
        """Apple原则：数据验证集中化"""
        required_fields = ['nickname', 'bank_name', 'statement_day', 'due_date_type', 'due_date_value']
        
        for field in required_fields:
            if field not in card_data or not card_data[field]:
                return False, f"缺少必要字段: {field}"
        
        # Validate ranges
        if not (1 <= card_data['statement_day'] <= 28):
            return False, "账单日必须在1-28之间"
        
        if card_data['due_date_type'] == 'fixed_day' and not (1 <= card_data['due_date_value'] <= 28):
            return False, "还款日必须在1-28之间"
        
        return True, ""
    
    @staticmethod
    def safe_get_card(nickname: str) -> tuple[Optional[Dict], Optional[str]]:
        """Apple原则：安全的数据获取，避免异常传播"""
        try:
            import database as db
            card = db.get_card_by_nickname(nickname)
            if not card:
                return None, "card_not_found"
            return card, None
        except Exception as e:
            logging.error(f"Database error getting card {nickname}: {e}")
            return None, "database_error"