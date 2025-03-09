# GTD Inbox for Telegram

A Telegram bot for managing personal GTD inbox with voice transcription capabilities.

## Features

- Add text items to your inbox via text or voice
- Process inbox items one by one

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/coignard/inbox-bot.git
   cd inbox-bot
   ```

2. Create a virtual environment and install dependencies:
   ```
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Create a `.env` file based on the example:
   ```
   cp .env.example .env
   ```

4. Edit the `.env` file with your configuration:
   - Add your Telegram Bot API token (get one from [@BotFather](https://t.me/BotFather))
   - Add your OpenAI API key for voice transcription
   - Set your authorized Telegram user ID

## Usage

Run the bot:

```
python .
```

### Bot Commands

- `/start` - Start or restart the bot
- `/process` - Process items in your inbox

### Functionality

- Send any text message to add it to your inbox
- Send voice messages to transcribe and add them to your inbox
- Use the ▶️ button to start processing your inbox
- Use ✅ to mark item as processed
- Use ⏹️ to stop processing

## License

MIT
