# handlers.py
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler, MessageHandler, 
    filters, CallbackQueryHandler
)
import logging
from datetime import datetime, date, timedelta
import calendar as py_calendar

from config import ADMIN_USER_ID
import database as db
import core_logic
from apple_ux_enhancements import AppleStyleUX
from app_config import config

# 状态定义 (为 editcard 年费子菜单增加新状态)
(
    # addcard 流程
    ADD_BANK_NAME, ADD_LAST_FOUR, ADD_NICKNAME, ADD_STATEMENT_DAY, 
    ADD_STATEMENT_INCLUSIVE, ADD_DUE_DATE_TYPE, ADD_DUE_DATE_VALUE, 
    ADD_CURRENCY_TYPE, ADD_ANNUAL_FEE_AMOUNT, ADD_ANNUAL_FEE_DATE, ADD_HAS_WAIVER,
    
    # editcard 流程
    EDIT_CHOOSE_CARD, EDIT_MAIN_MENU, EDIT_GET_VALUE,
    EDIT_STATEMENT_INCLUSIVE, EDIT_CURRENCY_TYPE,
    EDIT_DUE_DATE_TYPE, EDIT_DUE_DATE_VALUE,
    EDIT_FEE_SUB_MENU, EDIT_FEE_AMOUNT, EDIT_FEE_DATE, EDIT_HAS_WAIVER,
    EDIT_WAIVER_STATUS,

    # delcard 流程
    DEL_CARD_CHOOSE
) = range(24)

EDITABLE_FIELDS = {
    'nickname': '别名',
    'last_four_digits': '后四位',
    'bank_name': '银行',
    'statement_day': '账单日',
    'statement_day_inclusive': '账单日规则',
    'due_date_rule': '还款规则',
    'currency_type': '币种支持',
    'annual_fee': '年费信息'
}

def format_card_name(card: dict) -> str:
    """统一格式化卡片名称，格式为: 别名 (银行-后四位)"""
    if not card:
        return "未知卡片"
    
    nickname = card.get('nickname', '未命名')
    bank = card.get('bank_name', '未知银行')
    last_four = card.get('last_four_digits', '****')
    
    return f"{nickname} ({bank}-{last_four})"

def _format_card_summary(card: dict) -> str:
    """Apple原则：单一职责 - 专门格式化卡片摘要信息"""
    due_rule = f"每月{card['due_date_value']}号" if card['due_date_type'] == 'fixed_day' else f"账单日后{card['due_date_value']}天"
    currency_map = {"local": "人民币", "foreign": "外币", "all": "全币种"}
    currency_text = currency_map.get(card['currency_type'], card['currency_type'])
    
    info_parts = [
        f"• 账单日：{card['statement_day']}号",
        f"• 还款：{due_rule}",
        f"• 币种：{currency_text}"
    ]
    
    if card.get('annual_fee_amount', 0) > 0:
        fee_status = "已豁免" if card.get('is_waived_for_cycle') else "待处理"
        info_parts.append(f"• 年费：¥{card['annual_fee_amount']} ({fee_status})")
    
    return "📋 <b>当前信息概览</b>\n" + "\n".join(info_parts) + "\n"

def _format_primary_recommendation(best_card_info: dict) -> str:
    """Apple原则：专门格式化主要推荐信息"""
    card_name = AppleStyleUX.format_card_name_simple(best_card_info['card'])
    days = best_card_info['days']
    due_date_str = best_card_info['due_date'].strftime('%m月%d日')
    
    # Apple原则：简化条件逻辑
    advice_map = {
        (40, float('inf')): ("大额消费首选", "💎"),
        (25, 40): ("计划性消费推荐", "✨"),
        (15, 25): ("日常消费适用", "👍"),
        (0, 15): ("仅限小额消费", "⚠️")
    }
    
    advice, emoji = next((v for k, v in advice_map.items() if k[0] <= days < k[1]), ("适中消费", "💡"))
    
    return (
        f"🎯 <b>智能推荐</b>\n\n"
        f"{emoji} <b>{card_name}</b>\n"
        f"⏰ {days}天免息期 (至{due_date_str})\n"
        f"💡 {advice}"
    )

async def auth_guard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """检查用户是否是管理员，不是则礼貌拒绝"""
    user_id = update.effective_user.id
    if user_id != ADMIN_USER_ID:
        if update.message:
            await update.message.reply_text("抱歉，这是一个私人机器人。")
        elif update.callback_query:
            await update.callback_query.answer("抱歉，这是一个私人机器人。", show_alert=True)
        return False
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth_guard(update, context): return
    
    cards = db.get_all_cards()
    greeting = AppleStyleUX.get_smart_greeting(cards)
    insights = AppleStyleUX.get_proactive_insights(cards)
    recommendation = AppleStyleUX.get_smart_recommendations(cards)
    
    # Apple-style: Lead with the most important information
    welcome_parts = [f"👋 {greeting}"]
    
    # Add proactive insights if available
    if insights:
        welcome_parts.append("\n".join(insights))
    
    # Add primary recommendation
    if recommendation['primary']:
        rec_text = recommendation['primary']
        if recommendation['secondary']:
            rec_text += f"\n{recommendation['secondary']}"
        welcome_parts.append(rec_text)
    
    # Complete command menu - Apple style: organized and comprehensive
    welcome_parts.append(
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💳 <b>卡片管理</b>\n"
        "/addcard - 添加新卡片\n"
        "/editcard - 编辑卡片信息\n" 
        "/delcard - 删除卡片\n\n"
        "📊 <b>查看信息</b>\n"
        "/cards - 卡片组合概览\n"
        "/ask - 智能消费建议\n"
        "/calendar - 还款日历视图\n\n"
        "⚙️ <b>其他功能</b>\n"
        "/checkfees - 手动年费检查\n"
        "/cancel - 取消当前操作"
    )
    
    welcome_text = "\n\n".join(welcome_parts)
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await auth_guard(update, context): return ConversationHandler.END
    
    # 检查用户是否在进行某个操作
    operation_type = "操作"
    if 'new_card' in context.user_data:
        operation_type = "添加卡片"
    elif 'edit_nickname' in context.user_data:
        operation_type = "编辑卡片"
    
    if context.user_data:
        context.user_data.clear()
    
    await update.message.reply_text(
        f"✅ <b>{operation_type}已取消</b>\n\n"
        f"💡 您可以：\n"
        f"• /start - 查看所有功能\n"
        f"• /cards - 查看现有卡片\n"
        f"• /ask - 获取消费建议",
        parse_mode=ParseMode.HTML
    )
    return ConversationHandler.END

# --- /addcard 流程 ---
async def add_card_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await auth_guard(update, context): return ConversationHandler.END
    
    # 显示当前已有卡片数量
    existing_cards = db.get_all_cards()
    card_count_info = f"当前已有 {len(existing_cards)} 张卡片" if existing_cards else "这是您的第一张卡片"
    
    await update.message.reply_text(
        f"🎉 <b>添加新信用卡</b>\n"
        f"📊 {card_count_info}\n\n"
        f"让我们开始设置您的新卡片信息：\n\n"
        f"<b>步骤 1/9: 发卡银行</b>\n"
        f"请输入发卡银行名称（如：招商银行、工商银行）\n\n"
        f"💡 <i>提示：输入简短易记的名称即可</i>\n"
        f"🚫 随时输入 /cancel 取消操作",
        parse_mode=ParseMode.HTML
    )
    context.user_data['new_card'] = {}
    return ADD_BANK_NAME

async def add_get_bank_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    bank_name = update.message.text
    if not bank_name or bank_name.isspace():
        await update.message.reply_text("银行名称不能为空，请重新输入。")
        return ADD_BANK_NAME
    
    bank_name = bank_name.strip()
    if len(bank_name) > 50:
        await update.message.reply_text("银行名称过长，请输入50个字符以内的名称。")
        return ADD_BANK_NAME
    
    context.user_data['new_card']['bank_name'] = bank_name
    await update.message.reply_text(
        f"✅ 银行：<b>{bank_name}</b>\n\n"
        f"<b>步骤 2/9: 卡号后四位</b>\n"
        f"请输入信用卡号的后四位数字\n\n"
        f"💡 <i>用于区分同一银行的不同卡片</i>\n"
        f"🔒 <i>仅存储后四位，保护您的隐私</i>", 
        parse_mode=ParseMode.HTML
    )
    return ADD_LAST_FOUR

async def add_get_last_four(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if not (text.isdigit() and len(text) == 4):
        await update.message.reply_text("格式无效，请输入4位数字。")
        return ADD_LAST_FOUR
    context.user_data['new_card']['last_four_digits'] = text
    await update.message.reply_text(
        f"✅ 后四位：<b>{text}</b>\n\n"
        f"<b>步骤 3/9: 卡片别名</b>\n"
        f"请为这张卡取一个独特的别名\n\n"
        f"💡 <i>建议格式：银行+特色，如'招行小红卡'、'工行白金卡'</i>\n"
        f"🎯 <i>别名将用于快速识别和选择卡片</i>", 
        parse_mode=ParseMode.HTML
    )
    return ADD_NICKNAME

async def add_get_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    nickname = update.message.text.strip()
    if not nickname:
        await update.message.reply_text("别名不能为空，请重新输入。")
        return ADD_NICKNAME
    
    if len(nickname) > 50:
        await update.message.reply_text("别名过长，请输入50个字符以内的别名。")
        return ADD_NICKNAME
    
    if db.get_card_by_nickname(nickname):
        await update.message.reply_text(f"别名【{nickname}】已存在，请换一个。")
        return ADD_NICKNAME
    
    context.user_data['new_card']['nickname'] = nickname
    await update.message.reply_text(
        f"✅ 别名：<b>{nickname}</b>\n\n"
        f"<b>步骤 4/9: 账单日</b>\n"
        f"请输入这张卡的账单日（每月几号出账单）\n\n"
        f"💡 <i>建议选择1-28号，避免月末日期问题</i>\n"
        f"📊 <i>账单日影响免息期计算</i>", 
        parse_mode=ParseMode.HTML
    )
    return ADD_STATEMENT_DAY

async def add_get_statement_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        day = int(update.message.text)
        if not 1 <= day <= 28: 
            raise ValueError()
        
        # 给出月末日期的友好提示
        warning_msg = ""
        if day > 28:
            warning_msg = "\n⚠️ 注意：月末日期可能在某些月份不存在，建议选择1-28号。"
        elif day > 25:
            warning_msg = "\n💡 提示：选择的日期接近月末，请确认银行支持。"
            
        context.user_data['new_card']['statement_day'] = day
        keyboard = [[
            InlineKeyboardButton("计入本期", callback_data="add_inclusive_true"),
            InlineKeyboardButton("计入下期", callback_data="add_inclusive_false"),
        ]]
        await update.message.reply_text(
            f"✅ 账单日：每月<b>{day}号</b>{warning_msg}\n\n"
            f"<b>步骤 5/9: 账单日规则</b>\n"
            f"账单日当天的消费，计入本期还是下期账单？\n\n"
            f"💡 <i>大部分银行选择\"计入下期\"</i>\n"
            f"📋 <i>这影响消费的免息期计算</i>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
        return ADD_STATEMENT_INCLUSIVE
    except (ValueError, TypeError):
        await update.message.reply_text("请输入有效的日期数字（1-28）。")
        return ADD_STATEMENT_DAY

async def add_get_statement_inclusive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    is_inclusive = query.data == 'add_inclusive_true'
    context.user_data['new_card']['statement_day_inclusive'] = is_inclusive
    choice_text = "计入本期" if is_inclusive else "计入下期"
    await query.edit_message_text(text=f"账单日规则已选择：{choice_text}")
    keyboard = [[
        InlineKeyboardButton("固定的某一天", callback_data="add_due_fixed_day"),
        InlineKeyboardButton("账单日后N天", callback_data="add_due_days_after"),
    ]]
    await context.bot.send_message(chat_id=query.message.chat_id, text="好的。还款日是如何计算的？",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ADD_DUE_DATE_TYPE

async def add_get_due_date_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    due_type = 'fixed_day' if query.data == 'add_due_fixed_day' else 'days_after'
    context.user_data['new_card']['due_date_type'] = due_type
    choice_text = "固定的某一天" if due_type == 'fixed_day' else "账单日后N天"
    await query.edit_message_text(text=f"还款日类型已选择：{choice_text}")
    prompt_text = "是在每月的几号还款？（请输入数字1-28）" if due_type == 'fixed_day' else "是在账单日后多少天还款？（请输入数字）"
    await context.bot.send_message(chat_id=query.message.chat_id, text=prompt_text)
    return ADD_DUE_DATE_VALUE

async def add_get_due_date_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        value = int(update.message.text)
        due_type = context.user_data['new_card']['due_date_type']
        
        if due_type == 'fixed_day':
            if not 1 <= value <= 28:
                await update.message.reply_text("还款日请输入1-28之间的数字，避免月末日期问题。")
                return ADD_DUE_DATE_VALUE
        else:  # days_after
            if not 1 <= value <= 60:
                await update.message.reply_text("账单日后天数请输入1-60之间的合理数字。")
                return ADD_DUE_DATE_VALUE
        
        context.user_data['new_card']['due_date_value'] = value
        keyboard = [[
            InlineKeyboardButton("本币", callback_data="add_curr_local"),
            InlineKeyboardButton("外币", callback_data="add_curr_foreign"),
            InlineKeyboardButton("都支持", callback_data="add_curr_all"),
        ]]
        await update.message.reply_text("这张卡主要用于什么消费？", reply_markup=InlineKeyboardMarkup(keyboard))
        return ADD_CURRENCY_TYPE
    except (ValueError, TypeError):
        await update.message.reply_text("请输入有效的数字。")
        return ADD_DUE_DATE_VALUE

async def add_get_currency_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    type_map = {"add_curr_local": "local", "add_curr_foreign": "foreign", "add_curr_all": "all"}
    choice_map_text = {"add_curr_local": "本币", "add_curr_foreign": "外币", "add_curr_all": "都支持"}
    currency_type = type_map[query.data]
    context.user_data['new_card']['currency_type'] = currency_type
    await query.edit_message_text(text=f"币种支持已选择：{choice_map_text[query.data]}")
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="这张卡的年费是多少？（如果无年费，请输入 0）"
    )
    return ADD_ANNUAL_FEE_AMOUNT

async def add_get_annual_fee(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        fee = int(update.message.text)
        context.user_data['new_card']['annual_fee_amount'] = fee
        if fee == 0:
            return await finalize_add_card(update, context)
        else:
            await update.message.reply_text("年费通常在每年的几月几号收取？（请输入月份和日期，例如 08-15）")
            return ADD_ANNUAL_FEE_DATE
    except (ValueError, TypeError):
        await update.message.reply_text("请输入有效的数字。")
        return ADD_ANNUAL_FEE_AMOUNT

async def add_get_annual_fee_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        # 验证日期格式和有效性
        date_obj = datetime.strptime(update.message.text, '%m-%d')
        month, day = date_obj.month, date_obj.day
        
        # 检查日期是否合理（避免2月30日等无效日期）
        try:
            # 测试在非闰年是否有效
            datetime(2023, month, day)
        except ValueError:
            await update.message.reply_text("日期无效，请输入有效的月-日组合，例如 08-15。注意2月只有28天。")
            return ADD_ANNUAL_FEE_DATE
            
        fee_date = date_obj.strftime('%m-%d')
        context.user_data['new_card']['annual_fee_date'] = fee_date
        keyboard = [[
            InlineKeyboardButton("是", callback_data="add_waiver_true"),
            InlineKeyboardButton("否", callback_data="add_waiver_false"),
        ]]
        await update.message.reply_text("是否有豁免条件？", reply_markup=InlineKeyboardMarkup(keyboard))
        return ADD_HAS_WAIVER
    except ValueError:
        await update.message.reply_text("格式无效，请输入 MM-DD 格式的日期，例如 08-15。")
        return ADD_ANNUAL_FEE_DATE

async def add_get_has_waiver(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    has_waiver = query.data == 'add_waiver_true'
    context.user_data['new_card']['has_waiver'] = has_waiver
    choice_text = "是" if has_waiver else "否"
    await query.edit_message_text(text=f"支持豁免已选择：{choice_text}")
    return await finalize_add_card(update, context)

async def finalize_add_card(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    card_data = context.user_data['new_card']
    card_data.setdefault('annual_fee_amount', 0)
    card_data.setdefault('annual_fee_date', None)
    card_data.setdefault('has_waiver', False)
    card_data.setdefault('is_waived_for_cycle', False)
    if card_data.get('annual_fee_date'):
        today = date.today()
        month, day = map(int, card_data['annual_fee_date'].split('-'))
        fee_date_this_year = core_logic.safe_create_date(today.year, month, day)
        card_data['waiver_reset_date'] = fee_date_this_year.isoformat() if fee_date_this_year >= today else fee_date_this_year.replace(year=today.year + 1).isoformat()
    else:
        card_data['waiver_reset_date'] = None
    
    chat_id = update.effective_chat.id
    if db.add_card(card_data):
        # Apple-style: Simple success with immediate value
        card_name = AppleStyleUX.format_card_name_simple(card_data)
        days, due_date = core_logic.get_interest_free_period(card_data)
        
        # Apple-style contextual advice
        if days >= 40:
            advice = "大额消费的完美时机"
        elif days >= 25:
            advice = "适合计划性消费"
        else:
            advice = "适合日常消费"
        
        success_message = (
            f"✅ <b>{card_name} 已添加</b>\n\n"
            f"⏰ {days}天免息期\n"
            f"💡 {advice}\n\n"
            f"/ask 获取智能建议"
        )
        
        await context.bot.send_message(chat_id=chat_id, text=success_message, parse_mode=ParseMode.HTML)
    else:
        # Apple-style: Clear, actionable error message
        error_message = (
            f"❌ <b>Could not add card</b>\n\n"
            f"The nickname '{card_data['nickname']}' may already exist\n\n"
            f"/cards to see existing cards"
        )
        await context.bot.send_message(chat_id=chat_id, text=error_message, parse_mode=ParseMode.HTML)
    
    context.user_data.clear()
    return ConversationHandler.END


# --- /editcard 流程 ---
async def edit_card_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await auth_guard(update, context): return ConversationHandler.END
    cards = db.get_all_cards()
    if not cards:
        await update.message.reply_text("您还没有卡片可以编辑。")
        return ConversationHandler.END
    keyboard = [[InlineKeyboardButton(format_card_name(c), callback_data=f"edit_card_{c['nickname']}")] for c in cards]
    await update.message.reply_text("请选择您要编辑的卡片：", reply_markup=InlineKeyboardMarkup(keyboard))
    return EDIT_CHOOSE_CARD

async def edit_show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    nickname = context.user_data.get('edit_nickname')
    if not nickname: 
        return
    
    # Apple原则：缓存数据，避免重复查询
    card = context.user_data.get('edit_card_cache')
    if not card:
        card = db.get_card_by_nickname(nickname)
        if not card:
            msg = "❌ <b>错误</b>\n\n未找到该卡片或已被删除。\n\n💡 使用 /cards 查看现有卡片"
            if query: 
                await query.edit_message_text(text=msg, parse_mode=ParseMode.HTML)
            else: 
                await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
            return
        context.user_data['edit_card_cache'] = card

    # Apple原则：提取复杂逻辑到专门函数
    current_info = _format_card_summary(card)
    
    keyboard = []
    row = []
    for field, name in EDITABLE_FIELDS.items():
        row.append(InlineKeyboardButton(name, callback_data=f"edit_field_{field}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row: keyboard.append(row)
    keyboard.append([InlineKeyboardButton("✅ 完成编辑", callback_data="edit_field_done")])
    
    card_name_str = format_card_name(card)
    message_text = (
        f"✏️ <b>编辑卡片</b>\n"
        f"💳 <b>{card_name_str}</b>\n\n"
        f"{current_info}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"请选择要修改的项目："
    )
    
    if query:
        await query.edit_message_text(text=message_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    elif update.message:
        await update.message.reply_text(text=message_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)

async def edit_choose_card(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    nickname = query.data.split("edit_card_")[1]
    context.user_data['edit_nickname'] = nickname
    await edit_show_main_menu(update, context) 
    return EDIT_MAIN_MENU

async def edit_main_menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    field_to_edit = query.data.split("edit_field_")[1]
    
    if field_to_edit == 'done':
        card = db.get_card_by_nickname(context.user_data['edit_nickname'])
        await query.edit_message_text(text=f"卡片【{format_card_name(card)}】已编辑完毕。")
        context.user_data.clear()
        return ConversationHandler.END

    context.user_data['edit_field'] = field_to_edit
    
    if field_to_edit == 'statement_day_inclusive':
        keyboard = [[
            InlineKeyboardButton("计入本期", callback_data="edit_inclusive_true"),
            InlineKeyboardButton("计入下期", callback_data="edit_inclusive_false"),
        ]]
        await query.edit_message_text(text="请选择新的<b>账单日规则</b>：", reply_markup=InlineKeyboardMarkup(keyboard))
        return EDIT_STATEMENT_INCLUSIVE

    if field_to_edit == 'due_date_rule':
        keyboard = [[
            InlineKeyboardButton("固定的某一天", callback_data="edit_due_fixed_day"),
            InlineKeyboardButton("账单日后N天", callback_data="edit_due_days_after"),
        ]]
        await query.edit_message_text(text="请选择新的<b>还款规则类型</b>：", reply_markup=InlineKeyboardMarkup(keyboard))
        return EDIT_DUE_DATE_TYPE

    if field_to_edit == 'currency_type':
        keyboard = [[
            InlineKeyboardButton("本币", callback_data="edit_curr_local"),
            InlineKeyboardButton("外币", callback_data="edit_curr_foreign"),
            InlineKeyboardButton("都支持", callback_data="edit_curr_all"),
        ]]
        await query.edit_message_text(text="请选择新的<b>币种支持</b>：", reply_markup=InlineKeyboardMarkup(keyboard))
        return EDIT_CURRENCY_TYPE
        
    if field_to_edit == 'annual_fee':
        await query.edit_message_text(text="请输入新的<b>年费金额</b>（无则输入0）：")
        return EDIT_FEE_AMOUNT

    field_name_cn = EDITABLE_FIELDS.get(field_to_edit, field_to_edit)
    await query.edit_message_text(text=f"好的，请输入新的“<b>{field_name_cn}</b>”：")
    return EDIT_GET_VALUE

async def edit_get_simple_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    new_value = update.message.text.strip()
    nickname = context.user_data['edit_nickname']
    field = context.user_data['edit_field']
    
    # 添加输入验证
    if field in ['nickname', 'bank_name'] and len(new_value) > 50:
        await update.message.reply_text("输入过长，请输入50个字符以内的内容。")
        return EDIT_GET_VALUE
    
    if not new_value:
        await update.message.reply_text("输入不能为空，请重新输入。")
        return EDIT_GET_VALUE
    
    # 检查别名唯一性
    if field == 'nickname' and new_value != nickname:
        if db.get_card_by_nickname(new_value):
            await update.message.reply_text(f"别名【{new_value}】已存在，请换一个。")
            return EDIT_GET_VALUE
    
    if db.update_card(nickname, {field: new_value}):
        if field == 'nickname':
            context.user_data['edit_nickname'] = new_value
        field_name_cn = EDITABLE_FIELDS.get(field, field)
        await update.message.reply_text(f"✅ {field_name_cn}更新成功！")
    else:
        await update.message.reply_text("❌ 更新失败，请检查输入格式或稍后重试。")
    await edit_show_main_menu(update, context)
    return EDIT_MAIN_MENU

async def edit_get_statement_inclusive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    nickname = context.user_data['edit_nickname']
    new_value = (query.data == 'edit_inclusive_true')
    
    if db.update_card(nickname, {'statement_day_inclusive': new_value}):
        await query.message.reply_text(f"✅ “账单日规则”更新成功！")
    else:
        await query.message.reply_text("❌ 更新失败。")
    await edit_show_main_menu(update, context)
    return EDIT_MAIN_MENU

async def edit_get_currency_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    nickname = context.user_data['edit_nickname']
    type_map = {"edit_curr_local": "local", "edit_curr_foreign": "foreign", "edit_curr_all": "all"}
    new_value = type_map[query.data]
    
    if db.update_card(nickname, {'currency_type': new_value}):
        await query.message.reply_text(f"✅ “币种支持”更新成功！")
    else:
        await query.message.reply_text("❌ 更新失败。")
    await edit_show_main_menu(update, context)
    return EDIT_MAIN_MENU

async def edit_get_due_date_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data['edit_due_type'] = 'fixed_day' if query.data == 'edit_due_fixed_day' else 'days_after'
    prompt_text = "请输入新的还款日（每月几号，1-28）：" if context.user_data['edit_due_type'] == 'fixed_day' else "请输入新的还款天数（账单日后几天）："
    await query.edit_message_text(text=prompt_text)
    return EDIT_DUE_DATE_VALUE

async def edit_get_due_date_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        new_value = int(update.message.text)
        nickname = context.user_data['edit_nickname']
        due_type = context.user_data['edit_due_type']
        updates = {'due_date_type': due_type, 'due_date_value': new_value}
        if db.update_card(nickname, updates):
            await update.message.reply_text("✅ 还款规则更新成功！")
        else:
            await update.message.reply_text("❌ 更新失败，请检查输入格式或稍后重试。")
    except (ValueError, TypeError):
        await update.message.reply_text("请输入有效的数字。")
        return EDIT_DUE_DATE_VALUE
    await edit_show_main_menu(update, context)
    return EDIT_MAIN_MENU

async def edit_show_fee_submenu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    nickname = context.user_data['edit_nickname']
    card = db.get_card_by_nickname(nickname)
    status_text = "已豁免" if card.get('is_waived_for_cycle') else "待处理"
    message_text = (
        f"正在管理 <b>{format_card_name(card)}</b> 的年费信息。\n\n"
        f"• <b>当前豁免状态:</b> {status_text}\n\n"
        "请选择您要进行的操作："
    )
    keyboard = [
        [InlineKeyboardButton("更新本周期豁免状态", callback_data="edit_fee_status")],
        [InlineKeyboardButton("修改年费规则(金额/日期等)", callback_data="edit_fee_rules")],
        [InlineKeyboardButton("<< 返回编辑主菜单", callback_data="edit_fee_back")],
    ]
    if query:
        await query.edit_message_text(text=message_text, reply_markup=InlineKeyboardMarkup(keyboard))
    elif update.message:
        await update.message.reply_text(text=message_text, reply_markup=InlineKeyboardMarkup(keyboard))

async def edit_fee_submenu_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    action = query.data.split("edit_fee_")[1]
    if action == 'back':
        await edit_show_main_menu(update, context)
        return EDIT_MAIN_MENU
    elif action == 'rules':
        await query.edit_message_text(text="请输入新的<b>年费金额</b>（无则输入0）：")
        return EDIT_FEE_AMOUNT
    elif action == 'status':
        keyboard = [[
            InlineKeyboardButton("标记为“已豁免”", callback_data="edit_waiver_set_true"),
            InlineKeyboardButton("标记为“待处理”", callback_data="edit_waiver_set_false"),
        ]]
        await query.edit_message_text(text="请更新本周期的豁免状态：", reply_markup=InlineKeyboardMarkup(keyboard))
        return EDIT_WAIVER_STATUS

async def edit_get_waiver_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    nickname = context.user_data['edit_nickname']
    new_status = (query.data == 'edit_waiver_set_true')
    if db.update_card(nickname, {'is_waived_for_cycle': new_status}):
        await query.message.reply_text("✅ 豁免状态更新成功！")
    else:
        await query.message.reply_text("❌ 更新失败。")
    await edit_show_fee_submenu(update, context)
    return EDIT_FEE_SUB_MENU

async def edit_get_fee_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        fee = int(update.message.text)
        nickname = context.user_data['edit_nickname']
        if fee == 0:
            updates = {'annual_fee_amount': 0, 'annual_fee_date': None, 'has_waiver': False, 'is_waived_for_cycle': False}
            if db.update_card(nickname, updates):
                await update.message.reply_text("✅ 已将年费设置为 0，并清空相关信息。")
            else:
                await update.message.reply_text("❌ 更新失败。")
            await edit_show_main_menu(update, context)
            return EDIT_MAIN_MENU
        else:
            db.update_card(nickname, {'annual_fee_amount': fee})
            await update.message.reply_text("请输入新的年费收取日 (MM-DD):")
            return EDIT_FEE_DATE
    except (ValueError, TypeError):
        await update.message.reply_text("请输入有效的数字。")
        return EDIT_FEE_AMOUNT

async def edit_get_fee_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        fee_date_str = datetime.strptime(update.message.text, '%m-%d').strftime('%m-%d')
        nickname = context.user_data['edit_nickname']
        db.update_card(nickname, {'annual_fee_date': fee_date_str})
        keyboard = [[
            InlineKeyboardButton("是", callback_data="edit_waiver_true"),
            InlineKeyboardButton("否", callback_data="edit_waiver_false"),
        ]]
        await update.message.reply_text("是否有豁免条件？", reply_markup=InlineKeyboardMarkup(keyboard))
        return EDIT_HAS_WAIVER
    except ValueError:
        await update.message.reply_text("格式无效，请输入 MM-DD 格式的日期。")
        return EDIT_FEE_DATE

async def edit_get_has_waiver(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    has_waiver = query.data == 'edit_waiver_true'
    nickname = context.user_data['edit_nickname']
    if db.update_card(nickname, {'has_waiver': has_waiver}):
        await query.message.reply_text("✅ 年费信息更新完毕！")
    else:
        await query.message.reply_text("❌ 更新失败。")
    await edit_show_fee_submenu(update, context)
    return EDIT_FEE_SUB_MENU
async def list_cards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth_guard(update, context): return
    cards = db.get_all_cards()
    
    if not cards:
        await update.message.reply_text(
            "💳 <b>卡片组合</b>\n\n"
            "暂无卡片\n"
            "添加第一张卡片开始使用\n\n"
            "/addcard",
            parse_mode=ParseMode.HTML
        )
        return

    # Apple-style: Show summary first, then details
    summary = AppleStyleUX.generate_notification_summary(cards)
    best_card = AppleStyleUX.get_best_card_for_today(cards)
    
    message = f"💳 <b>卡片组合</b> ({len(cards)}张)\n"
    if summary != "All set":
        message += f"{summary}\n"
    message += "\n"
    
    # Show best card prominently (Apple's "featured" approach)
    if best_card:
        card_name = AppleStyleUX.format_card_name_simple(best_card['card'])
        days = best_card['days']
        
        if days >= 30:
            status_emoji = "🟢"
        elif days >= 15:
            status_emoji = "🟡"
        else:
            status_emoji = "🔴"
        
        message += f"⭐ <b>{card_name}</b>\n{status_emoji} {days}天免息期\n\n"
    
    # Apple-style: Simplified list view
    today = date.today()
    cards_with_period = []
    for card in cards:
        days, due_date = core_logic.get_interest_free_period(card, today)
        cards_with_period.append((card, days, due_date))
    
    cards_with_period.sort(key=lambda x: x[1], reverse=True)
    
    message += "<b>全部卡片</b>\n"
    for card, days, due_date in cards_with_period:
        card_name = AppleStyleUX.format_card_name_simple(card)
        
        # 使用统一的状态系统 - 基于免息期长度
        if days >= 30:
            status = "🟢"  # 充足免息期
        elif days >= 15:
            status = "🟡"  # 适中免息期
        else:
            status = "🔴"  # 较短免息期
        
        message += f"{status} {card_name} • {days}天\n"
    
    message += f"\n/ask 获取智能建议"
    await update.message.reply_text(message, parse_mode=ParseMode.HTML)

async def get_recommendation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Apple原则：简化复杂逻辑，专注核心功能"""
    if not await auth_guard(update, context): 
        return
    
    cards = db.get_all_cards()
    if not cards:
        await update.message.reply_text(
            "🎯 <b>智能建议</b>\n\n"
            "添加卡片开始智能分析\n\n"
            "• 最优免息期\n"
            "• 消费策略\n"
            "• 个性推荐",
            parse_mode=ParseMode.HTML
        )
        return
    
    today = datetime.now()
    today_str = today.strftime('%Y年%m月%d日')
    weekday = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][today.weekday()]
    
    # 计算所有卡片的免息期
    recommendations = []
    for card in cards:
        days, due_date = core_logic.get_interest_free_period(card)
        recommendations.append({'card': card, 'days': days, 'due_date': due_date})
    
    recommendations.sort(key=lambda x: x['days'], reverse=True)

    # 分别获取本币和外币卡片推荐
    local_cards = [r for r in recommendations if r['card']['currency_type'] in ['local', 'all']][:3]
    foreign_cards = [r for r in recommendations if r['card']['currency_type'] in ['foreign', 'all']][:3]

    message = f"🎯 <b>智能消费建议</b>\n📅 {today_str} {weekday}\n"
    message += "="*30 + "\n\n"
    
    # 人民币消费建议
    message += "💰 <b>人民币消费推荐</b>\n"
    if local_cards:
        for i, rec in enumerate(local_cards):
            rank_emoji = ["🥇", "🥈", "🥉"][i]
            card_name_str = format_card_name(rec['card'])
            due_date_str = rec['due_date'].strftime('%m月%d日')
            
            # 根据免息期长短给出不同的建议
            if rec['days'] >= 40:
                advice = "💎 超长免息期，大额消费首选"
            elif rec['days'] >= 25:
                advice = "✨ 免息期较长，适合中大额消费"
            elif rec['days'] >= 15:
                advice = "👍 免息期适中，日常消费推荐"
            else:
                advice = "⚠️ 免息期较短，建议小额消费"
            
            message += f"{rank_emoji} <b>{card_name_str}</b>\n"
            message += f"    ⏰ 免息期: <b>{rec['days']}天</b> (至{due_date_str})\n"
            message += f"    💡 {advice}\n\n"
    else:
        message += "❌ 暂无支持人民币的卡片\n\n"

    # 外币消费建议
    message += "🌍 <b>外币消费推荐</b>\n"
    if foreign_cards:
        for i, rec in enumerate(foreign_cards):
            rank_emoji = ["🥇", "🥈", "🥉"][i]
            card_name_str = format_card_name(rec['card'])
            due_date_str = rec['due_date'].strftime('%m月%d日')
            
            if rec['days'] >= 40:
                advice = "🌟 海外消费/网购首选"
            elif rec['days'] >= 25:
                advice = "✈️ 出境旅游推荐"
            elif rec['days'] >= 15:
                advice = "🛒 外币小额消费适用"
            else:
                advice = "⚠️ 免息期较短，谨慎使用"
            
            message += f"{rank_emoji} <b>{card_name_str}</b>\n"
            message += f"    ⏰ 免息期: <b>{rec['days']}天</b> (至{due_date_str})\n"
            message += f"    💡 {advice}\n\n"
    else:
        message += "❌ 暂无支持外币的卡片\n\n"

    # 添加智能提醒
    message += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    message += "🔔 <b>智能提醒</b>\n"
    
    # 检查即将到来的账单日
    upcoming_statements = []
    for card in cards:
        next_stmt = core_logic.get_next_calendar_statement_date(today.date(), card['statement_day'])
        days_to_stmt = (next_stmt - today.date()).days
        if days_to_stmt <= 3:
            upcoming_statements.append((card, days_to_stmt))
    
    if upcoming_statements:
        message += "📋 近期账单日提醒:\n"
        for card, days in upcoming_statements:
            if days == 0:
                message += f"• 🔴 {format_card_name(card)} 今日出账单\n"
            else:
                message += f"• 🟡 {format_card_name(card)} {days}天后出账单\n"
    else:
        message += "✅ 近期无账单日，消费无忧\n"

    await update.message.reply_text(message, parse_mode=ParseMode.HTML)

async def del_card_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await auth_guard(update, context): return ConversationHandler.END
    cards = db.get_all_cards()
    if not cards:
        await update.message.reply_text("您没有任何卡片可以删除。")
        return ConversationHandler.END
    
    keyboard = [[InlineKeyboardButton(f"删除【{format_card_name(c)}】", callback_data=f"del_confirm_{c['nickname']}")] for c in cards]
    await update.message.reply_text("请选择您要删除的卡片：", 
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return DEL_CARD_CHOOSE

async def del_card_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    nickname = query.data.split("del_confirm_")[1]
    card = db.get_card_by_nickname(nickname)
    
    if card and db.delete_card(nickname):
        card_name_str = format_card_name(card)
        await query.edit_message_text(text=f"卡片【{card_name_str}】已成功删除。")
    else:
        await query.edit_message_text(text="删除失败，请稍后再试。")

    return ConversationHandler.END
async def calendar_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /calendar 命令和日历翻页的回调"""
    if not await auth_guard(update, context): return
    
    query = update.callback_query
    today = date.today()
    
    # 确定要显示的月份
    year, month = today.year, today.month
    if query:
        await query.answer()
        # 从回调数据中解析出要导航到的年和月
        _, _, nav_year, nav_month = query.data.split('_')
        year, month = int(nav_year), int(nav_month)

    # 获取该月份的还款事件
    cards = db.get_all_cards()
    events = {}
    for card in cards:
        # 我们需要检查整个月份的事件，而不仅仅是未来45天
        # 此处逻辑需要调整，为简化，我们暂时只高亮当月事件
        next_due_date = core_logic.get_next_due_date(card, date(year, month, 1))
        if next_due_date.year == year and next_due_date.month == month:
            if next_due_date.day not in events: events[next_due_date.day] = []
            events[next_due_date.day].append(format_card_name(card))

    # --- 构建日历键盘 ---
    keyboard = []
    
    # 1. 标题行
    header_text = f"📅 {year}年 {month}月 - 还款日历"

    # 2. 导航行
    prev_month_date = date(year, month, 1) - timedelta(days=1)
    next_month_date = date(year, month, 1) + timedelta(days=32)
    nav_row = [
        InlineKeyboardButton("<<", callback_data=f"cal_nav_{prev_month_date.year}_{prev_month_date.month}"),
        InlineKeyboardButton(f"{month}月", callback_data="cal_noop"), # No operation
        InlineKeyboardButton(">>", callback_data=f"cal_nav_{next_month_date.year}_{next_month_date.month}"),
    ]
    keyboard.append(nav_row)
    
    # 3. 今日按钮行（如果不是当前月份）
    if year != today.year or month != today.month:
        today_row = [
            InlineKeyboardButton("📅 回到今日", callback_data=f"cal_nav_{today.year}_{today.month}")
        ]
        keyboard.append(today_row)

    # 3. 星期行
    week_days = ["一", "二", "三", "四", "五", "六", "日"]
    keyboard.append([InlineKeyboardButton(day, callback_data="cal_noop") for day in week_days])
    
    # 4. 日期行
    month_calendar = py_calendar.monthcalendar(year, month)
    for week in month_calendar:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="cal_noop"))
            else:
                if day in events:
                    # 计算该日期与今天的差值来确定状态
                    event_date = date(year, month, day)
                    days_diff = (event_date - today).days
                    status_emoji = config.get_event_status_emoji(days_diff)
                    button_text = f"{status_emoji} {day}"
                    callback_data = f"cal_day_{year}-{month}-{day}"
                else:
                    button_text = str(day)
                    callback_data = "cal_noop"
                row.append(InlineKeyboardButton(button_text, callback_data=callback_data))
        keyboard.append(row)

    # --- 构建底部图例和事件列表 ---
    event_list_str = f"\n📋 <b>{year}年{month}月还款事件</b>\n"
    if not events:
        event_list_str += "🎉 本月无还款事件，消费无忧！\n"
    else:
        event_list_str += f"共 {len(events)} 个还款日，涉及 {sum(len(cards) for cards in events.values())} 张卡片：\n\n"
        for day in sorted(events.keys()):
            cards_list = events[day]
            # 计算距离今天的天数
            event_date = date(year, month, day)
            days_diff = (event_date - today).days
            
            # 使用统一的状态系统
            emoji = config.get_event_status_emoji(days_diff)
            time_info = config.get_event_status_text(days_diff)
            
            event_list_str += f"{emoji} <b>{day}日</b> ({time_info})\n"
            for card_name in cards_list:
                event_list_str += f"   💳 {card_name}\n"
            event_list_str += "\n"
    
    # 添加图例说明
    # 添加图例说明
    legend_str = (
        "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{config.calendar_legend}\n\n"
        "💡 <i>点击日期可查看详细信息</i>"
    )

    final_text = header_text + "\n" + event_list_str + legend_str

    # --- 发送或编辑消息 ---
    if query:
        # 如果是点击按钮触发，则编辑原消息
        await query.edit_message_text(
            text=final_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
    else:
        # 如果是命令触发，则发送新消息
        await update.message.reply_text(
            text=final_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )

# --- 自动化任务函数 ---

# Removed duplicate function - keeping only the one at the end of file
async def _perform_fee_check(bot, chat_id: int):
    """封装了年费检查的核心逻辑，可被任何方式调用"""
    today = date.today()
    logging.info(f"为 Chat ID {chat_id} 执行年费检查...")
    
    cards_with_fee = [card for card in db.get_all_cards() if card.get('annual_fee_date')]
    reminders_sent = 0
    
    for card in cards_with_fee:
        if card['waiver_reset_date']:
            reset_date = date.fromisoformat(card['waiver_reset_date'])
            if today >= reset_date:
                logging.info(f"卡片 {card['nickname']} 的豁免周期已重置。")
                db.update_card(card['nickname'], {'is_waived_for_cycle': False})
                next_reset_date = reset_date.replace(year=reset_date.year + 1)
                db.update_card(card['nickname'], {'waiver_reset_date': next_reset_date.isoformat()})
                card['is_waived_for_cycle'] = False

        if not card['has_waiver'] or card['is_waived_for_cycle']:
            continue

        month, day = map(int, card['annual_fee_date'].split('-'))
        next_fee_date = date(today.year, month, day)
        if next_fee_date < today:
            next_fee_date = next_fee_date.replace(year=today.year + 1)
        
        days_until_fee = (next_fee_date - today).days
        reminder_windows = [60, 30, 15, 7, 3, 1]
        if days_until_fee in reminder_windows:
            card_name_str = format_card_name(card)
            
            # 根据剩余天数调整提醒紧急程度
            if days_until_fee <= 3:
                urgency_emoji = "🚨"
                urgency_text = "紧急提醒"
            elif days_until_fee <= 7:
                urgency_emoji = "⚠️"
                urgency_text = "重要提醒"
            else:
                urgency_emoji = "💡"
                urgency_text = "友情提醒"
            
            message = (
                f"{urgency_emoji} <b>{urgency_text} - 年费即将到期</b>\n\n"
                f"💳 <b>{card_name_str}</b>\n"
                f"📅 年费日期：{card['annual_fee_date']}\n"
                f"💰 年费金额：¥{card['annual_fee_amount']}\n"
                f"⏰ 剩余时间：<b>{days_until_fee}天</b>\n\n"
                f"🎯 <b>这张卡支持年费豁免</b>\n"
                f"请确认您是否已完成本年度的豁免条件\n\n"
                f"💡 <i>常见豁免条件：刷卡次数、消费金额等</i>"
            )
            keyboard = [[
                InlineKeyboardButton("✅ 已完成豁免，标记为已处理", callback_data=f"waiver_confirm_{card['nickname']}")
            ]]
            await bot.send_message(
                chat_id=chat_id,
                text=message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.HTML
            )
            reminders_sent += 1
    
    return reminders_sent

# --- 自动化与手动触发函数 ---
async def daily_check_job(context: ContextTypes.DEFAULT_TYPE):
    """由 JobQueue 每日自动调用的函数"""
    job = context.job
    await _perform_fee_check(context.bot, job.chat_id)

async def force_check_fees(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """【新增】处理 /checkfees 命令，手动触发年费检查"""
    if not await auth_guard(update, context): return
    
    await update.message.reply_text("正在手动触发年费检查...")
    
    reminders_sent = await _perform_fee_check(context.bot, update.effective_chat.id)
    
    if reminders_sent > 0:
        await update.message.reply_text(f"检查完成，共发送了 {reminders_sent} 条提醒。")
    else:
        await update.message.reply_text("检查完成，当前没有需要提醒的年费项目。")

async def calendar_date_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth_guard(update, context): return
    
    query = update.callback_query
    await query.answer()
    
    # 解析日期
    date_str = query.data.split("cal_day_")[1]  # 格式: YYYY-MM-DD
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        await query.edit_message_text("日期格式错误")
        return
    
    today = date.today()
    days_diff = (selected_date - today).days
    
    # 获取该日期的所有事件
    cards = db.get_all_cards()
    events = []
    
    for card in cards:
        # 检查还款日
        next_due_date = core_logic.get_next_due_date(card, selected_date)
        if next_due_date == selected_date:
            events.append({
                'type': 'due_date',
                'card': card,
                'description': '还款日'
            })
        
        # 检查账单日
        if card['statement_day'] == selected_date.day:
            events.append({
                'type': 'statement_date',
                'card': card,
                'description': '账单日'
            })
        
        # 检查年费日
        if card.get('annual_fee_date'):
            fee_month, fee_day = map(int, card['annual_fee_date'].split('-'))
            if selected_date.month == fee_month and selected_date.day == fee_day:
                events.append({
                    'type': 'annual_fee',
                    'card': card,
                    'description': f'年费 ¥{card["annual_fee_amount"]}'
                })
    
    # 构建详细信息
    date_str_cn = selected_date.strftime('%Y年%m月%d日')
    weekday = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][selected_date.weekday()]
    
    # 使用统一的状态系统
    status_emoji = config.get_event_status_emoji(days_diff)
    time_info = config.get_event_status_text(days_diff)
    
    message = f"📅 <b>{date_str_cn} {weekday}</b>\n"
    message += f"{status_emoji} {time_info}\n\n"
    
    if not events:
        message += "📋 <b>当日事件</b>\n"
        message += "暂无金融事件\n\n"
        
        # 如果是未来日期，提供消费建议
        # 如果是未来日期，提供消费建议
        if days_diff > 0:
            best_card = AppleStyleUX.get_best_card_for_date(cards, selected_date)
            if best_card:
                card_name = AppleStyleUX.format_card_name_simple(best_card['card'])
                message += f"💡 <b>消费建议</b>\n"
                message += f"推荐使用 {card_name}\n"
                message += f"免息期：{best_card['days']}天\n\n"
    else:
        message += f"📋 <b>当日事件</b> ({len(events)}项)\n"
        for event in events:
            card_name = format_card_name(event['card'])
            message += f"• {event['description']} - {card_name}\n"
        message += "\n"
    
    # 添加未来7天预览（仅对未来日期）
    if days_diff >= 0:
        upcoming_events = []
        for i in range(1, 8):
            future_date = selected_date + timedelta(days=i)
            for card in cards:
                next_due = core_logic.get_next_due_date(card, future_date)
                if next_due == future_date:
                    upcoming_events.append((future_date, card, '还款'))
        
        if upcoming_events:
            message += "🔮 <b>未来7天预览</b>\n"
            for future_date, card, event_type in upcoming_events[:3]:  # 最多显示3个
                days_later = (future_date - selected_date).days
                card_name = AppleStyleUX.format_card_name_simple(card)
                message += f"• {days_later}天后 {event_type} - {card_name}\n"
            message += "\n"
    
    # 添加快捷操作按钮
    keyboard = [
        [
            InlineKeyboardButton("💡 获取建议", callback_data="cal_ask_recommendation"),
            InlineKeyboardButton("🏠 返回主页", callback_data="cal_home")
        ],
        [InlineKeyboardButton("📅 返回日历", callback_data=f"cal_nav_{selected_date.year}_{selected_date.month}")]
    ]
    
    await query.edit_message_text(
        text=message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )

async def calendar_quick_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理日历快捷操作"""
    if not await auth_guard(update, context):
        return
    query = update.callback_query
    await query.answer()

    if query.data == "cal_ask_recommendation":
        # 创建一个模拟的 message 对象用于发送新消息
        class MockMessage:
            def __init__(self, chat_id):
                self.chat = type('obj', (object,), {'id': chat_id})
            
            async def reply_text(self, text, parse_mode=None):
                await context.bot.send_message(
                    chat_id=self.chat.id,
                    text=text,
                    parse_mode=parse_mode
                )
        
        # 创建新的 update 对象用于调用 get_recommendation
        mock_update = type('obj', (object,), {
            'message': MockMessage(query.message.chat_id),
            'effective_user': update.effective_user,
            'effective_chat': update.effective_chat
        })
        await get_recommendation(mock_update, context)
        
    elif query.data == "cal_home":
        # 创建一个模拟的 message 对象用于发送新消息
        class MockMessage:
            def __init__(self, chat_id):
                self.chat = type('obj', (object,), {'id': chat_id})
            
            async def reply_text(self, text, parse_mode=None):
                await context.bot.send_message(
                    chat_id=self.chat.id,
                    text=text,
                    parse_mode=parse_mode
                )
        
        # 创建新的 update 对象用于调用 start
        mock_update = type('obj', (object,), {
            'message': MockMessage(query.message.chat_id),
            'effective_user': update.effective_user,
            'effective_chat': update.effective_chat
        })
        await start(mock_update, context)
        
    elif query.data.startswith("cal_remind_"):
        # 设置提醒功能（简化版）
        await query.edit_message_text(
            text="🔔 <b>提醒功能</b>\n\n"
                 "提醒功能正在开发中\n"
                 "目前系统会自动在年费到期前提醒\n\n"
                 "💡 您可以使用 /checkfees 手动检查年费状态",
            parse_mode=ParseMode.HTML
        )
    elif query.data.startswith("cal_note_"):
        # 添加备注功能（简化版）
        await query.edit_message_text(
            text="📝 <b>备注功能</b>\n\n"
                 "备注功能正在开发中\n"
                 "您可以通过编辑卡片来添加相关信息\n\n"
                 "💡 使用 /editcard 编辑卡片详细信息",
            parse_mode=ParseMode.HTML
        )

async def confirm_waiver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理用户点击"确认豁免"按钮的回调"""
    if not await auth_guard(update, context): return
    
    query = update.callback_query
    await query.answer("正在更新状态...")
    nickname = query.data.split("waiver_confirm_")[1]
    card = db.get_card_by_nickname(nickname)
    
    if card and db.update_card(nickname, {'is_waived_for_cycle': True}):
        card_name_str = format_card_name(card)
        await query.edit_message_text(
            text=f"✅ 收到！【{card_name_str}】已标记为本年度豁免，在下一个年费周期前将不再提醒您。"
        )
    else:
        await query.edit_message_text(text="状态更新失败，请稍后重试。")
