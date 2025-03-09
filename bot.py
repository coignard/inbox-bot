import os
import tempfile
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, BotCommand
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, Filters,
    CallbackContext, CallbackQueryHandler
)
from num2words import num2words
import openai
import sqlite3
from dotenv import load_dotenv

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")


class InboxBot:
    def __init__(self, token, authorized_user_id, database_path):
        self.token = token
        self.authorized_user_id = authorized_user_id
        self.database_path = database_path
        self.updater = Updater(token, use_context=True)
        self.dispatcher = self.updater.dispatcher
        self.job_queue = self.updater.job_queue
        self.transcription_data = {}

        self._setup_handlers()
        self._set_commands()
        self._create_table()

    def _create_connection(self):
        return sqlite3.connect(self.database_path, check_same_thread=False)

    def _create_table(self):
        conn = self._create_connection()
        cursor = conn.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS inbox (content TEXT)')
        conn.commit()
        conn.close()

    def _setup_handlers(self):
        self.dispatcher.add_handler(CommandHandler("start", self.start))
        self.dispatcher.add_handler(CommandHandler("process", self.process_inbox))
        self.dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, self.handle_message))
        self.dispatcher.add_handler(MessageHandler(Filters.voice, self.handle_voice_message))
        self.dispatcher.add_handler(CallbackQueryHandler(self.button))

    def _set_commands(self):
        commands = [
            BotCommand('process', 'Traiter la boîte de réception')
        ]
        self.updater.bot.set_my_commands(commands)

    def _is_authorized(self, user_id):
        return user_id == self.authorized_user_id

    def get_count(self):
        conn = self._create_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM inbox')
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def add_item(self, content):
        conn = self._create_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO inbox (content) VALUES (?)', (content,))
        conn.commit()
        conn.close()

    def get_first_item(self):
        conn = self._create_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT rowid, content FROM inbox LIMIT 1')
        item = cursor.fetchone()
        conn.close()
        return item

    def delete_item(self, item_id):
        conn = self._create_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM inbox WHERE rowid = ?', (item_id,))
        conn.commit()
        conn.close()

    def get_message_text(self, count):
        if count == 0:
            return "0️⃣ Inbox zero!"

        number_word = num2words(count, lang='fr')
        item_word = 'élément' if count == 1 else 'éléments'
        count_emojis = ''.join(f"{num}️⃣" for num in str(count))
        return f"{count_emojis} Vous avez {number_word} {item_word} dans votre boîte de réception"

    def get_inline_keyboard(self, count):
        if count > 0:
            keyboard = [[InlineKeyboardButton("▶️", callback_data='process')]]
            return InlineKeyboardMarkup(keyboard)
        return None

    def start(self, update: Update, context: CallbackContext):
        if not self._is_authorized(update.effective_user.id):
            return

        count = self.get_count()
        keyboard = self.get_inline_keyboard(count)
        message = update.message.reply_text(
            self.get_message_text(count),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
        context.bot_data['message_id'] = message.message_id

    def handle_message(self, update: Update, context: CallbackContext):
        if not self._is_authorized(update.effective_user.id):
            return

        self.add_item(update.message.text)
        update.message.delete()

        count = self.get_count()
        keyboard = self.get_inline_keyboard(count)

        context.bot.edit_message_text(
            self.get_message_text(count),
            chat_id=update.effective_chat.id,
            message_id=context.bot_data['message_id'],
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )

    def transcribe_audio(self, file_path):
        try:
            with open(file_path, "rb") as audio_file:
                transcript = openai.Audio.transcribe("whisper-1", audio_file)
            return transcript["text"]
        except Exception as e:
            print(f"Error transcribing audio: {e}")
            return None

    def handle_voice_message(self, update: Update, context: CallbackContext):
        if not self._is_authorized(update.effective_user.id):
            return

        file = context.bot.getFile(update.message.voice.file_id)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg", dir='/tmp') as temp_file:
            file_path = temp_file.name
            file.download(custom_path=file_path)

        context.bot.delete_message(
            chat_id=update.message.chat_id,
            message_id=update.message.message_id
        )

        context.bot.edit_message_text(
            "🎤 Transcription du message...",
            chat_id=update.effective_chat.id,
            message_id=context.bot_data['message_id']
        )

        transcription = self.transcribe_audio(file_path)

        if transcription:
            self.transcription_data[update.effective_chat.id] = transcription
            keyboard = [
                [
                    InlineKeyboardButton("✅", callback_data='save_transcription'),
                    InlineKeyboardButton("⏹️", callback_data='cancel_transcription')
                ]
            ]

            context.bot.edit_message_text(
                f"🎤 {transcription}",
                parse_mode=ParseMode.MARKDOWN,
                chat_id=update.effective_chat.id,
                message_id=context.bot_data['message_id'],
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            error_message = "❌ Échec de la transcription du message."
            count = self.get_count()
            keyboard = self.get_inline_keyboard(count)

            context.bot.edit_message_text(
                f"{error_message}\n\n{self.get_message_text(count)}",
                chat_id=update.effective_chat.id,
                message_id=context.bot_data['message_id'],
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard
            )

        os.remove(file_path)

    def process_inbox(self, update: Update, context: CallbackContext, from_button=False):
        if not self._is_authorized(update.effective_user.id):
            return

        if not from_button:
            update.message.delete()

        count = self.get_count()
        if count == 0:
            return

        item = self.get_first_item()
        if item:
            item_id, content = item
            context.bot_data['process_inbox'] = item_id

            number_word = num2words(count, lang='fr')
            item_word = 'élément' if count == 1 else 'éléments'
            count_emojis = ''.join(f"{num}️⃣" for num in str(count))
            text = f"```\n{content}```\n\n{count_emojis} Vous avez {number_word} {item_word} dans votre boîte de réception"

            keyboard = [
                [
                    InlineKeyboardButton("✅", callback_data='done'),
                    InlineKeyboardButton("⏹️", callback_data='stop')
                ]
            ]

            context.bot.edit_message_text(
                text,
                chat_id=update.effective_chat.id,
                message_id=context.bot_data['message_id'],
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )

    def button(self, update: Update, context: CallbackContext):
        query = update.callback_query
        query.answer()

        if query.data == 'process':
            self.process_inbox(update, context, from_button=True)
            return

        if query.data == 'save_transcription':
            transcription = self.transcription_data.pop(query.message.chat_id, None)
            if transcription:
                self.add_item(transcription)

                count = self.get_count()
                keyboard = self.get_inline_keyboard(count)

                query.edit_message_text(
                    self.get_message_text(count),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=keyboard
                )
            return

        if query.data == 'cancel_transcription':
            self.transcription_data.pop(query.message.chat_id, None)
            count = self.get_count()
            keyboard = self.get_inline_keyboard(count)

            query.edit_message_text(
                self.get_message_text(count),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard
            )
            return

        item_id = context.bot_data.get('process_inbox')

        if query.data == 'done' and item_id:
            self.delete_item(item_id)

        count = self.get_count()
        keyboard = self.get_inline_keyboard(count)

        if count == 0 or query.data == 'stop':
            context.bot.edit_message_text(
                self.get_message_text(count),
                chat_id=query.message.chat_id,
                message_id=query.message.message_id,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard
            )
            context.bot_data.pop('process_inbox', None)
        else:
            item = self.get_first_item()
            if item:
                item_id, content = item
                context.bot_data['process_inbox'] = item_id

                number_word = num2words(count, lang='fr')
                item_word = 'élément' if count == 1 else 'éléments'
                count_emojis = ''.join(f"{num}️⃣" for num in str(count))
                text = f"```\n{content}```\n\n{count_emojis} Vous avez {number_word} {item_word} dans votre boîte de réception"

                keyboard = [
                    [
                        InlineKeyboardButton("✅", callback_data='done'),
                        InlineKeyboardButton("⏹️", callback_data='stop')
                    ]
                ]

                context.bot.edit_message_text(
                    text,
                    chat_id=query.message.chat_id,
                    message_id=query.message.message_id,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.MARKDOWN
                )

    def send_initial_message(self, context: CallbackContext):
        count = self.get_count()
        keyboard = self.get_inline_keyboard(count)

        message = context.bot.send_message(
            chat_id=self.authorized_user_id,
            text=self.get_message_text(count),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
        context.bot_data['message_id'] = message.message_id

    def run(self):
        self.job_queue.run_once(self.send_initial_message, 0)
        self.updater.start_polling()
        self.updater.idle()
