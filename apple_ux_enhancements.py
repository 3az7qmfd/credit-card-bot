# Apple-Style UX Enhancements for Credit Card Bot
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Tuple
import database as db
import core_logic

class AppleStyleUX:
    """Apple-inspired UX enhancements focusing on simplicity and intelligence"""
    
    # Apple原则：常量提取，避免魔法数字
    TIME_PERIODS = {
        (5, 12): "早上好",
        (12, 18): "下午好",
        (18, 24): "晚上好",
        (0, 5): "晚上好"
    }
    
    @staticmethod
    def get_smart_greeting(cards: List[Dict]) -> str:
        """Generate contextual greeting based on time and user state"""
        hour = datetime.now().hour
        card_count = len(cards)
        
        # Apple原则：简化时间判断逻辑
        time_greeting = next(
            (greeting for (start, end), greeting in AppleStyleUX.TIME_PERIODS.items() 
             if start <= hour < end), 
            "您好"
        )
        
        # Apple原则：使用字典映射替代多重if-else
        greeting_templates = {
            0: f"{time_greeting}，准备添加第一张卡片？",
            1: f"{time_greeting}，您的卡片已就绪"
        }
        
        return greeting_templates.get(card_count, f"{time_greeting}，{card_count}张卡片运行中")
    
    @staticmethod
    def get_proactive_insights(cards: List[Dict]) -> List[str]:
        """Generate proactive insights like Apple's Siri suggestions"""
        insights = []
        today = date.today()
        
        # Check for upcoming statement dates
        upcoming_statements = []
        for card in cards:
            next_stmt = core_logic.get_next_calendar_statement_date(today, card['statement_day'])
            days_until = (next_stmt - today).days
            if days_until <= 2:
                upcoming_statements.append((card, days_until))
        
        if upcoming_statements:
            if len(upcoming_statements) == 1:
                card, days = upcoming_statements[0]
                if days == 0:
                    insights.append("💳 今日生成账单")
                else:
                    insights.append(f"📅 {days}天后出账单")
            else:
                insights.append(f"📋 {len(upcoming_statements)}个账单即将到期")
        
        # Check for optimal spending opportunities
        best_card = AppleStyleUX.get_best_card_for_today(cards)
        if best_card:
            days = best_card['days']
            if days >= 45:
                insights.append("✨ 绝佳消费时机")
            elif days >= 30:
                insights.append("👍 良好消费机会")
        
        return insights[:2]  # Apple-style: show max 2 key insights
    
    # Apple原则：配置常量化
    SCORING_CONFIG = {
        'local_currency_bonus': 5,
        'upcoming_statement_penalty': 10,
        'statement_warning_days': 3
    }
    
    @staticmethod
    def get_best_card_for_today(cards: List[Dict]) -> Dict[str, Any]:
        """Get the single best card for today - Apple's "one best choice" philosophy"""
        if not cards:
            return None
        
        today = date.today()
        
        # Apple原则：使用列表推导式简化代码
        card_scores = [
            AppleStyleUX._calculate_card_score(card, today) 
            for card in cards
        ]
        
        # Apple原则：使用max函数的key参数
        return max(card_scores, key=lambda x: x['score'])
    
    @staticmethod
    def _calculate_card_score(card: Dict, today: date) -> Dict[str, Any]:
        """Apple原则：提取复杂计算逻辑到单独方法"""
        days, due_date = core_logic.get_interest_free_period(card, today)
        
        # Base score is the free period days
        score = days
        
        # Apply bonuses and penalties
        if card['currency_type'] in ['local', 'all']:
            score += AppleStyleUX.SCORING_CONFIG['local_currency_bonus']
        
        # Penalty for upcoming statements
        next_stmt = core_logic.get_next_calendar_statement_date(today, card['statement_day'])
        days_to_stmt = (next_stmt - today).days
        if days_to_stmt <= AppleStyleUX.SCORING_CONFIG['statement_warning_days']:
            score -= AppleStyleUX.SCORING_CONFIG['upcoming_statement_penalty']
        
        return {
            'card': card,
            'days': days,
            'due_date': due_date,
            'score': score
        }
    
    @staticmethod
    def format_card_name_simple(card: Dict) -> str:
        """Apple-style simple card naming"""
        # Extract bank name and make it concise
        bank = card.get('bank_name', '').replace('银行', '').replace('Bank', '')
        nickname = card.get('nickname', '')
        
        # Use nickname if it's short and descriptive, otherwise use bank
        if len(nickname) <= 8 and not nickname.lower().startswith(bank.lower()):
            return nickname
        else:
            last_four = card.get('last_four_digits', '****')
            return f"{bank} •{last_four}"
    
    @staticmethod
    def get_smart_recommendations(cards: List[Dict]) -> Dict[str, Any]:
        """Generate Apple-style smart recommendations"""
        if not cards:
            return {
                'primary': "添加第一张卡片开始使用",
                'secondary': None,
                'action': "/addcard"
            }
        
        best = AppleStyleUX.get_best_card_for_today(cards)
        if not best:
            return {
                'primary': "暂无最优卡片",
                'secondary': "检查卡片设置",
                'action': "/portfolio"
            }
        
        card_name = AppleStyleUX.format_card_name_simple(best['card'])
        days = best['days']
        
        if days >= 40:
            advice = "大额消费首选"
        elif days >= 25:
            advice = "计划性消费推荐"
        elif days >= 15:
            advice = "日常消费适用"
        else:
            advice = "仅限小额消费"
        
        return {
            'primary': f"推荐使用 {card_name}",
            'secondary': f"{days}天 • {advice}",
            'action': None
        }
    
    @staticmethod
    @staticmethod
    def get_best_card_for_date(cards: List[Dict], target_date: date) -> Dict[str, Any]:
        """Get the best card for a specific date"""
        if not cards:
            return None
        
        # Calculate scores for the target date
        card_scores = [
            AppleStyleUX._calculate_card_score_for_date(card, target_date) 
            for card in cards
        ]
        
        # Return the best card
        return max(card_scores, key=lambda x: x['score'])
    
    @staticmethod
    def _calculate_card_score_for_date(card: Dict, target_date: date) -> Dict[str, Any]:
        """Calculate card score for a specific date"""
        days, due_date = core_logic.get_interest_free_period(card, target_date)
        
        # Base score is the free period days
        score = days
        
        # Apply bonuses for currency support
        if card['currency_type'] in ['local', 'all']:
            score += AppleStyleUX.SCORING_CONFIG['local_currency_bonus']
        
        return {
            'card': card,
            'days': days,
            'due_date': due_date,
            'score': score
        }
    
    @staticmethod
    def generate_notification_summary(cards: List[Dict]) -> str:
        """Generate Apple-style notification summary"""
        insights = AppleStyleUX.get_proactive_insights(cards)
        recommendation = AppleStyleUX.get_smart_recommendations(cards)
        
        if not insights and recommendation['primary'] == "添加第一张卡片开始使用":
            return "💳 准备添加第一张卡片"
        
        summary_parts = []
        if insights:
            summary_parts.extend(insights)
        
        if recommendation['primary'] and not recommendation['primary'].startswith("添加"):
            summary_parts.append(recommendation['primary'])
        
        return " • ".join(summary_parts) if summary_parts else "一切就绪"
