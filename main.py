# main.py
import logging
import asyncio
from datetime import time
from zoneinfo import ZoneInfo
from telegram.ext import (
    Application, CommandHandler, ConversationHandler, MessageHandler, 
    filters, CallbackQueryHandler, Defaults
)
from telegram.constants import ParseMode

import config
import database
from handlers import (
    start, cancel, list_cards, get_recommendation, calendar_view, calendar_date_detail, calendar_quick_actions,
    add_card_start, add_get_bank_name, add_get_last_four, add_get_nickname,
    add_get_statement_day, add_get_statement_inclusive, add_get_due_date_type,
    add_get_due_date_value, add_get_currency_type, add_get_annual_fee,
    add_get_annual_fee_date, add_get_has_waiver,
    edit_card_start, edit_choose_card, edit_main_menu_router,
    edit_get_simple_value, edit_get_statement_inclusive, edit_get_currency_type,
    edit_get_due_date_type, edit_get_due_date_value,
    edit_show_fee_submenu, edit_fee_submenu_router, edit_get_waiver_status,
    edit_get_fee_amount, edit_get_fee_date, edit_get_has_waiver,
    del_card_start, del_card_confirm,
    daily_check_job, force_check_fees, confirm_waiver,
    ADD_BANK_NAME, ADD_LAST_FOUR, ADD_NICKNAME, ADD_STATEMENT_DAY, 
    ADD_STATEMENT_INCLUSIVE, ADD_DUE_DATE_TYPE, ADD_DUE_DATE_VALUE, 
    ADD_CURRENCY_TYPE, ADD_ANNUAL_FEE_AMOUNT, ADD_ANNUAL_FEE_DATE, ADD_HAS_WAIVER,
    EDIT_CHOOSE_CARD, EDIT_MAIN_MENU, EDIT_GET_VALUE, EDIT_STATEMENT_INCLUSIVE,
    EDIT_CURRENCY_TYPE, EDIT_DUE_DATE_TYPE, EDIT_DUE_DATE_VALUE,
    EDIT_FEE_SUB_MENU, EDIT_FEE_AMOUNT, EDIT_FEE_DATE, EDIT_HAS_WAIVER,
    EDIT_WAIVER_STATUS,
    DEL_CARD_CHOOSE
)

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def main() -> None:
    database.init_db()
    
    local_tz = ZoneInfo('Asia/Shanghai')
    defaults = Defaults(parse_mode=ParseMode.HTML, tzinfo=local_tz)
    application = Application.builder().token(config.config['telegram']['bot_token']).defaults(defaults).build()
    
    logging.info("Bot is starting...")

    add_card_conv = ConversationHandler(
        entry_points=[CommandHandler("addcard", add_card_start)],
        states={
            ADD_BANK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_get_bank_name)],
            ADD_LAST_FOUR: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_get_last_four)],
            ADD_NICKNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_get_nickname)],
            ADD_STATEMENT_DAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_get_statement_day)],
            ADD_STATEMENT_INCLUSIVE: [CallbackQueryHandler(pattern="^add_inclusive_", callback=add_get_statement_inclusive)],
            ADD_DUE_DATE_TYPE: [CallbackQueryHandler(pattern="^add_due_", callback=add_get_due_date_type)],
            ADD_DUE_DATE_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_get_due_date_value)],
            ADD_CURRENCY_TYPE: [CallbackQueryHandler(pattern="^add_curr_", callback=add_get_currency_type)],
            ADD_ANNUAL_FEE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_get_annual_fee)],
            ADD_ANNUAL_FEE_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_get_annual_fee_date)],
            ADD_HAS_WAIVER: [CallbackQueryHandler(pattern="^add_waiver_", callback=add_get_has_waiver)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False
    )
    
    edit_card_conv = ConversationHandler(
        entry_points=[CommandHandler("editcard", edit_card_start)],
        states={
            EDIT_CHOOSE_CARD: [CallbackQueryHandler(pattern="^edit_card_", callback=edit_choose_card)],
            EDIT_MAIN_MENU: [CallbackQueryHandler(pattern="^edit_field_", callback=edit_main_menu_router)],
            EDIT_GET_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_get_simple_value)],
            EDIT_STATEMENT_INCLUSIVE: [CallbackQueryHandler(pattern="^edit_inclusive_", callback=edit_get_statement_inclusive)],
            EDIT_CURRENCY_TYPE: [CallbackQueryHandler(pattern="^edit_curr_", callback=edit_get_currency_type)],
            EDIT_DUE_DATE_TYPE: [CallbackQueryHandler(pattern="^edit_due_", callback=edit_get_due_date_type)],
            EDIT_DUE_DATE_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_get_due_date_value)],
            EDIT_FEE_SUB_MENU: [CallbackQueryHandler(pattern="^edit_fee_", callback=edit_fee_submenu_router)],
            EDIT_FEE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_get_fee_amount)],
            EDIT_FEE_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_get_fee_date)],
            EDIT_HAS_WAIVER: [CallbackQueryHandler(pattern="^edit_waiver_", callback=edit_get_has_waiver)],
            EDIT_WAIVER_STATUS: [CallbackQueryHandler(pattern="^edit_waiver_set_", callback=edit_get_waiver_status)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False
    )

    del_card_conv = ConversationHandler(
        entry_points=[CommandHandler("delcard", del_card_start)],
        states={
            DEL_CARD_CHOOSE: [CallbackQueryHandler(pattern="^del_confirm_", callback=del_card_confirm)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(CommandHandler("cards", list_cards))
    application.add_handler(CommandHandler("ask", get_recommendation))
    application.add_handler(CommandHandler("calendar", calendar_view))
    application.add_handler(CommandHandler("checkfees", force_check_fees))
    
    application.add_handler(add_card_conv)
    application.add_handler(edit_card_conv)
    application.add_handler(del_card_conv)

    application.add_handler(CallbackQueryHandler(calendar_view, pattern="^cal_nav_"))
    application.add_handler(CallbackQueryHandler(calendar_date_detail, pattern="^cal_day_"))
    application.add_handler(CallbackQueryHandler(calendar_quick_actions, pattern="^cal_ask_recommendation$"))
    application.add_handler(CallbackQueryHandler(calendar_quick_actions, pattern="^cal_home$"))
    application.add_handler(CallbackQueryHandler(calendar_quick_actions, pattern="^cal_remind_"))
    application.add_handler(CallbackQueryHandler(calendar_quick_actions, pattern="^cal_note_"))
    application.add_handler(CallbackQueryHandler(pattern="^waiver_confirm_", callback=confirm_waiver))
    
    try:
        logging.info("Application starting...")
        await application.initialize()
        job_queue = application.job_queue
        job_queue.run_daily(
            daily_check_job, 
            time=time(hour=10, minute=0, second=0), 
            chat_id=config.ADMIN_USER_ID, 
            name="daily_fee_check"
        )
        await application.updater.start_polling()
        await application.start()
        logging.info("Daily jobs scheduled. Bot is now running.")
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot received stop signal.")
    finally:
        logging.info("Bot is shutting down...")
        if application.updater and application.updater.running:
            await application.updater.stop()
        if application.running:
            await application.stop()
        await application.shutdown()
        logging.info("Bot has shut down successfully.")

if __name__ == "__main__":
    asyncio.run(main())