import os
import json
import re
import asyncio
from telethon import TelegramClient, events, Button
from telethon.tl.types import DocumentAttributeAnimated
from telethon.utils import get_peer_id  # Key to get the correct ID format
from openai import OpenAI

# =============================================================================
#                           OPENAI CONFIG FOR TRANSLATION
# =============================================================================
OPENAI_API_KEY = (
    ""
)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# =============================================================================
#                         TELEGRAM CREDENTIALS
# =============================================================================
api_id = 123456
api_hash = ''
phone = ''  # forwarder user phone

# Bot token (inline menu):
BOT_TOKEN = ""

# =============================================================================
#                       FILE PATHS / JSON CONFIG
# =============================================================================
SOURCE_GROUPS_FILE = "bot_config/source_groups.json"
OFFENSIVE_WORDS_FILE = "bot_config/offensive_words.json"
MAPPINGS_FILE = "bot_config/message_mappings.json"

# =============================================================================
#         DESTINATION GROUP CHAT IDS (AS IN YOUR PREVIOUS CODE)
# =============================================================================
destination_group_chat_id_1 = 
destination_group_chat_id_2 = 
destination_group_chat_id_3 = 
test_destination_group_chat_id = 

# =============================================================================
#                     LOAD SOURCE GROUPS & OFFENSIVE WORDS
# =============================================================================
def load_source_groups(file_path):
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Source groups file not found: {file_path}")
        exit(1)
    except json.JSONDecodeError:
        print(f"Error decoding the source groups file: {file_path}")
        exit(1)

def load_offensive_words(file_path):
    try:
        with open(file_path, "r") as f:
            return set(json.load(f))
    except FileNotFoundError:
        print(f"Offensive words file not found: {file_path}")
        exit(1)
    except json.JSONDecodeError:
        print(f"Error decoding the offensive words file: {file_path}")
        exit(1)

def save_source_groups(file_path, data):
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)

source_groups = load_source_groups(SOURCE_GROUPS_FILE)
OFFENSIVE_WORDS = load_offensive_words(OFFENSIVE_WORDS_FILE)

# Extract from source_groups
source_group_chat_ids_set_1 = source_groups["set_1"]  # e.g. [-1001234567890, -1009876543210]
source_group_chat_ids_set_2 = source_groups["set_2"]
source_group_chat_ids_set_3 = source_groups["set_3"]
test_source_group_chat_id   = source_groups["test"]

# =============================================================================
#               TELETHON CLIENTS: FORWARDER + BOT
# =============================================================================
client_telegram = TelegramClient('session_name', api_id, api_hash)
bot = TelegramClient('bot_session_editor', api_id, api_hash)

# =============================================================================
#                   TRACKING / MAPPINGS
# =============================================================================
processed_messages = set()
sent_messages = set()
message_mappings = {}
reply_mappings = {}

try:
    with open(MAPPINGS_FILE, "r") as file:
        data = json.load(file)
        message_mappings = data.get("message_mappings", {})
        reply_mappings   = data.get("reply_mappings", {})
except (FileNotFoundError, json.JSONDecodeError):
    message_mappings = {}
    reply_mappings = {}

async def save_mappings():
    with open(MAPPINGS_FILE, "w") as file:
        json.dump({"message_mappings": message_mappings, "reply_mappings": reply_mappings}, file)

# =============================================================================
#                          FORWARDING LOGIC
# =============================================================================
def contains_offensive_words(message, offensive_words):
    if not message:
        return False
    message_lower = message.lower()
    for word in offensive_words:
        if re.search(rf'\b{re.escape(word)}\b', message_lower):
            return True
    return False

async def translate_message(message):
    """Translate an English message to Bulgarian using OpenAI API."""
    try:
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Translate the following English sentence into Bulgarian."},
                {"role": "user", "content": message}
            ],
            temperature=0.7,
            max_tokens=256,
            top_p=1
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error during translation: {e}")
        return "Translation error occurred."

async def forward_message(event, destination_chat_id, source_chat_id):
    """
    Forward messages while maintaining accurate reply mappings.
    Same as your code: block offensive, do translation, handle media, etc.
    """
    if event.id in processed_messages:
        print(f"Message ID {event.id} already processed, skipping.")
        return
    processed_messages.add(event.id)

    # Extract message text
    message_text = event.message.message if event.message else ""

    # Offensive words check
    if contains_offensive_words(message_text, OFFENSIVE_WORDS):
        print(f"Blocked message ID {event.id} from chat {source_chat_id} due to offensive content.")
        try:
            await event.reply("Your message contains prohibited content and was not forwarded.")
            print(f"Notified user about blocked message ID {event.id}.")
        except Exception as e:
            print(f"Failed to notify user about blocked message: {e}")
        return

    # Check if it's a reply
    reply_to_msg_id = None
    if event.is_reply:
        reply_to = await event.get_reply_message()
        if reply_to:
            source_reply_id = reply_to.id
            reply_mapping = message_mappings.get(str(source_chat_id), {}).get(str(source_reply_id), {})
            reply_to_msg_id = reply_mapping.get(str(destination_chat_id))

    # Handle media
    if (event.photo or
        (event.document and any(isinstance(attr, DocumentAttributeAnimated) for attr in event.document.attributes))
    ):
        file_path = await event.download_media()
        caption = event.message.message if event.message.message else None

        original_message = await client_telegram.send_file(
            destination_chat_id,
            file_path,
            caption=caption,
            reply_to=reply_to_msg_id
        )
        print(f"Media sent to destination group {destination_chat_id}")

        # Map
        if str(source_chat_id) not in message_mappings:
            message_mappings[str(source_chat_id)] = {}
        message_mappings[str(source_chat_id)][str(event.id)] = {
            str(destination_chat_id): original_message.id
        }
        await save_mappings()

        # Translate caption if any
        if caption:
            translated_caption = await translate_message(caption)
            if translated_caption:
                translated_message = await client_telegram.send_message(
                    destination_chat_id,
                    translated_caption,
                    reply_to=original_message.id
                )
                print(f"Translated caption sent as a reply in group {destination_chat_id}")

        if os.path.exists(file_path):
            os.remove(file_path)
        return

    # Handle plain text
    if event.message and event.message.message:
        msg_text = event.message.message
        translated_msg = await translate_message(msg_text)

        original_message = await client_telegram.send_message(
            destination_chat_id,
            msg_text,
            reply_to=reply_to_msg_id
        )
        print(f"Text message sent to destination group {destination_chat_id}")

        # Update mapping
        if str(source_chat_id) not in message_mappings:
            message_mappings[str(source_chat_id)] = {}
        message_mappings[str(source_chat_id)][str(event.id)] = {
            str(destination_chat_id): original_message.id
        }

        if reply_to_msg_id:
            if str(source_chat_id) not in reply_mappings:
                reply_mappings[str(source_chat_id)] = {}
            reply_mappings[str(source_chat_id)][str(event.id)] = {
                str(destination_chat_id): reply_to_msg_id
            }

        await save_mappings()

        # Send the translated text
        if translated_msg:
            await client_telegram.send_message(
                destination_chat_id,
                translated_msg,
                reply_to=original_message.id
            )
            print(f"Translated message sent as a reply in group {destination_chat_id}")

# =============================================================================
#               PER-SET EVENT HANDLERS (RE-REGISTER ON CHANGE)
# =============================================================================
handler_set_1_ref = None
handler_set_2_ref = None
handler_set_3_ref = None
handler_test_ref  = None

def register_handlers():
    """
    Re-register the event handlers for set_1, set_2, set_3, test
    so changes to `source_groups` take effect immediately.
    """
    global handler_set_1_ref, handler_set_2_ref, handler_set_3_ref, handler_test_ref

    # Remove old handlers if they exist
    if handler_set_1_ref:
        client_telegram.remove_event_handler(handler_set_1_ref)
        handler_set_1_ref = None
    if handler_set_2_ref:
        client_telegram.remove_event_handler(handler_set_2_ref)
        handler_set_2_ref = None
    if handler_set_3_ref:
        client_telegram.remove_event_handler(handler_set_3_ref)
        handler_set_3_ref = None
    if handler_test_ref:
        client_telegram.remove_event_handler(handler_test_ref)
        handler_test_ref = None

    # Re-assign from the in-memory `source_groups`
    set_1 = source_groups["set_1"]
    set_2 = source_groups["set_2"]
    set_3 = source_groups["set_3"]
    set_test = source_groups["test"]

    @client_telegram.on(events.NewMessage(chats=set_1))
    async def handler_set_1(event):
        await forward_message(event, destination_group_chat_id_1, event.chat_id)

    @client_telegram.on(events.NewMessage(chats=set_2))
    async def handler_set_2(event):
        await forward_message(event, destination_group_chat_id_2, event.chat_id)

    @client_telegram.on(events.NewMessage(chats=set_3))
    async def handler_set_3(event):
        await forward_message(event, destination_group_chat_id_3, event.chat_id)

    @client_telegram.on(events.NewMessage(chats=set_test))
    async def handler_test(event):
        await forward_message(event, test_destination_group_chat_id, event.chat_id)

    # Save references
    handler_set_1_ref = handler_set_1
    handler_set_2_ref = handler_set_2
    handler_set_3_ref = handler_set_3
    handler_test_ref  = handler_test

    print("[register_handlers] Updated set_1, set_2, set_3, test handlers with new groups.")

# Register them initially
register_handlers()

# =============================================================================
#                           BOT MENU TO EDIT GROUPS
# =============================================================================
USER_STATE = {}

def main_menu_text():
    txt = "📢 **Source Groups Editor** 📢\n\n"
    txt += f"**set_1**: {source_groups['set_1']}\n"
    txt += f"**set_2**: {source_groups['set_2']}\n"
    txt += f"**set_3**: {source_groups['set_3']}\n"
    txt += f"**test** : {source_groups['test']}\n\n"
    txt += "Use the buttons below to **edit** the source groups."
    return txt

def main_menu_buttons():
    return [
        [Button.inline("🔧 Edit Crypto Lion Vip", b"edit_set_1")],
        [Button.inline("🔧 Edit Crypto Lion", b"edit_set_2")],
        [Button.inline("🔧 Edit Crypto Lion 1", b"edit_set_3")],
        [Button.inline("🔧 Edit test group", b"edit_test")],
    ]

def set_menu_text(set_name):
    return f"🔄 **Editing {set_name}** 🔄\nCurrent groups: `{source_groups[set_name]}`\n\nChoose a group to **replace** or **add** a new one."

def set_menu_buttons(set_name):
    buttons = []
    for i, gid in enumerate(source_groups[set_name]):
        data = f"choose_src|{set_name}|{i}"
        label = f"➕ Source {i+1}: {gid}"
        buttons.append([Button.inline(label, data.encode('utf-8'))])
    if not source_groups[set_name]:
        data = f"choose_src|{set_name}|0"
        buttons.append([Button.inline("➕ Add first group", data.encode('utf-8'))])
    buttons.append([Button.inline("🔙 Back", b"back_main")])
    return buttons

async def get_all_dialogs():
    """
    Return (corrected_id, title) for each dialog. We use `get_peer_id(d.entity)`
    to ensure we store the actual ID (with -100 if supergroup).
    """
    dialogs = await client_telegram.get_dialogs(limit=None)
    results = []
    for d in dialogs:
        # We get the correct Telethon ID:
        real_id = get_peer_id(d.entity)
        title = d.name or "Untitled"
        results.append((real_id, title))
    # Sort by title
    results.sort(key=lambda x: x[1].lower())
    return results

def build_dialog_buttons(dialogs, set_name, index):
    btns = []
    for chat_id, title in dialogs:
        short_title = (title[:30] + "...") if len(title) > 30 else title
        # We store the final ID from get_peer_id
        data_str = f"replace_src|{set_name}|{index}|{chat_id}"
        btns.append([Button.inline(short_title, data_str.encode('utf-8'))])
    # Back
    back_str = f"back_set|{set_name}"
    btns.append([Button.inline("🔙 Back", back_str.encode('utf-8'))])
    return btns

@bot.on(events.NewMessage(pattern="/start"))
async def on_start(event):
    txt = main_menu_text()
    btns = main_menu_buttons()
    await event.respond(txt, buttons=btns)
    raise events.StopPropagation

@bot.on(events.CallbackQuery)
async def inline_handler(event):
    data = event.data.decode('utf-8')

    # BACK MAIN
    if data == "back_main":
        txt = main_menu_text()
        btns = main_menu_buttons()
        await event.edit(txt, buttons=btns)
        return

    # EDIT set_1 / set_2 / set_3 / test
    if data.startswith("edit_"):
        set_name = data.replace("edit_", "")
        txt = set_menu_text(set_name)
        btns = set_menu_buttons(set_name)
        await event.edit(txt, buttons=btns)
        return

    # BACK SET
    if data.startswith("back_set"):
        _, set_name = data.split("|", 1)
        txt = set_menu_text(set_name)
        btns = set_menu_buttons(set_name)
        await event.edit(txt, buttons=btns)
        return

    # CHOOSE SRC => show all user dialogs
    if data.startswith("choose_src"):
        _, set_name, idx_str = data.split("|")
        idx = int(idx_str)
        dialogs = await get_all_dialogs()
        text = f"📌 **Select a new group/chat to place at index {idx} in {set_name}.**"
        btns = build_dialog_buttons(dialogs, set_name, idx)
        await event.edit(text, buttons=btns)
        return

    # REPLACE SRC => update source_groups + re-register
    if data.startswith("replace_src"):
        _, set_name, idx_str, chat_id_str = data.split("|")
        idx = int(idx_str)
        new_chat_id = int(chat_id_str)

        # Expand if needed
        while len(source_groups[set_name]) <= idx:
            source_groups[set_name].append(None)
        source_groups[set_name][idx] = new_chat_id

        # Save to disk
        save_source_groups(SOURCE_GROUPS_FILE, source_groups)

        # Re-register handlers with the updated sets
        register_handlers()

        # Show updated main
        txt = main_menu_text()
        btns = main_menu_buttons()
        await event.edit(f"✅ **Updated {set_name}: {source_groups[set_name]}**\n\n{txt}", buttons=btns)
        return

# =============================================================================
#                                MAIN
# =============================================================================
def main():
    client_telegram.start(phone=phone)
    bot.start(bot_token=BOT_TOKEN)

    print("Monitoring groups for new messages. Bot is ready for config changes.")
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.gather(
        client_telegram.run_until_disconnected(),
        bot.run_until_disconnected()
    ))

if __name__ == "__main__":
    main()
