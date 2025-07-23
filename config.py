# config.py
import yaml
import os
import logging
from pathlib import Path
import dotenv
dotenv.load_dotenv()  # 加载 .env 文件中的环境变量

CONFIG_FILE = Path(__file__).parent / "config.yaml"

def load_config():
    """
    从 config.yaml 加载配置，并使用环境变量进行覆盖。
    优先级: 环境变量 > config.yaml
    """
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            if not config:
                raise ValueError("config.yaml 为空或格式不正确。")

        bot_token_from_env = os.getenv('TELEGRAM_BOT_TOKEN')
        if bot_token_from_env:
            config['telegram']['bot_token'] = bot_token_from_env
            logging.info("使用环境变量中的 TELEGRAM_BOT_TOKEN。")

        admin_id_from_env = os.getenv('ADMIN_USER_ID')
        if admin_id_from_env:
            try:
                config['admin']['user_id'] = int(admin_id_from_env)
                logging.info("使用环境变量中的 ADMIN_USER_ID。")
            except ValueError:
                raise ValueError("环境变量 ADMIN_USER_ID 必须是一个有效的整数。")

        if not config.get('telegram', {}).get('bot_token') or not config.get('admin', {}).get('user_id'):
            raise ValueError("关键配置 bot_token 或 admin_user_id 未能成功加载。请检查 config.yaml 或 .env 文件。")
            
        return config

    except FileNotFoundError:
        raise FileNotFoundError(f"配置文件 {CONFIG_FILE} 未找到。请根据模板创建。")
    except Exception as e:
        raise Exception(f"加载或解析配置时出错: {e}")

config = load_config()
ADMIN_USER_ID = config['admin']['user_id']