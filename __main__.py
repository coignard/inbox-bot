import os
from dotenv import load_dotenv
from bot import InboxBot

if __name__ == "__main__":
    load_dotenv()

    tg_bot_api_key = os.getenv("TG_BOT_API_KEY")
    authorized_user_id = int(os.getenv("AUTHORIZED_USER_ID"))
    database_path = os.getenv("DATABASE_PATH", "inbox.db")

    bot = InboxBot(tg_bot_api_key, authorized_user_id, database_path)
    bot.run()
