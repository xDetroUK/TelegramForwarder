Telegram Message Forwarder with AI Translation
🌐 Project Overview
I developed an advanced Telegram message forwarding system that:

Automatically forwards messages between groups

Translates content using OpenAI's GPT-3.5

Filters offensive language

Maintains conversation threads

Provides an interactive configuration interface

🔧 Key Features
Core Functionality
Multi-group forwarding with three configurable sets

AI-powered translation (English to Bulgarian)

Offensive content filtering with customizable word lists

Media handling (photos, GIFs, documents)

Reply chain preservation across forwarded messages

Management System
Interactive bot interface for configuration

Dynamic handler registration for live updates

JSON-based configuration for source/destination groups

Message tracking to prevent duplicates

🛠️ Technical Implementation
System Architecture
python
Copy
# Two parallel Telegram clients
client_telegram = TelegramClient(...)  # Main forwarding client
bot = TelegramClient(...)  # Configuration bot

# Core data structures
message_mappings = {}  # Tracks original->forwarded message IDs
reply_mappings = {}    # Maintains reply relationships
processed_messages = set()  # Prevents duplicate processing
Message Processing Flow
python
Copy
async def forward_message(event, destination_chat_id, source_chat_id):
    # 1. Check for offensive content
    if contains_offensive_words(message_text, OFFENSIVE_WORDS):
        await event.reply("Message blocked")
        return
    
    # 2. Handle media/files
    if event.photo or event.document:
        await handle_media_forward(event)
    
    # 3. Process text messages
    else:
        original = await send_original_text(event)
        translated = await translate_and_send(event)
        
    # 4. Update mappings
    update_message_mappings(source_chat_id, event.id, original.id)
Dynamic Event Handling
python
Copy
def register_handlers():
    # Can re-register handlers when config changes
    @client_telegram.on(events.NewMessage(chats=source_groups["set_1"]))
    async def handler_set_1(event):
        await forward_message(event, destination_group_chat_id_1)
🌟 Key Components
1. AI Translation Engine
python
Copy
async def translate_message(message):
    response = openai_client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Translate to Bulgarian"},
            {"role": "user", "content": message}
        ]
    )
    return response.choices[0].message.content
2. Interactive Configuration Bot
python
Copy
@bot.on(events.CallbackQuery)
async def inline_handler(event):
    if data.startswith("replace_src"):
        # Update group configuration
        source_groups[set_name][idx] = new_chat_id
        save_source_groups()
        register_handlers()  # Live reload
3. Message Tracking System
python
Copy
# Maintains relationships between original and forwarded messages
message_mappings = {
    "source_chat_id": {
        "original_msg_id": {
            "destination_chat_id": "forwarded_msg_id"
        }
    }
}
🚀 Usage
Configure Groups:

Edit source_groups.json or use the interactive bot

/start to access configuration menu

Run Forwarder:

bash
Copy
python telegram_forwarder.py
Features:

Automatic message forwarding

Real-time translation

Content moderation

Thread preservation

🔧 Technical Highlights
Robust Error Handling
python
Copy
try:
    await forward_message(event)
except Exception as e:
    print(f"Forwarding failed: {e}")
    await notify_admin(f"Error in {event.chat_id}: {str(e)}")
Efficient Media Handling
python
Copy
if event.photo or event.document:
    file = await event.download_media()
    await client.send_file(destination, file)
    os.remove(file)  # Cleanup
Dynamic Configuration
python
Copy
def register_handlers():
    # Can update handlers without restart
    client.remove_event_handler(old_handler)
    client.add_event_handler(new_handler)
📊 System Diagram
Copy
[Source Groups] → [Forwarder] → [Destination Groups]
       ↑               ↓               ↓
[Config Bot] ← [Mappings DB]   [AI Translation]
🛠️ Skills Demonstrated
System Architecture

Dual-client Telegram integration

Asynchronous message processing

State management across conversations

AI Integration

OpenAI API implementation

Context-aware translation

Error-tolerant design

Software Engineering

Configuration management

Dynamic event handling

Data persistence (JSON)

Interactive UI development
