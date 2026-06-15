import asyncio, os
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from dotenv import load_dotenv

load_dotenv('/home/agent/migration_agent/.env')

API_ID   = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")
PHONE    = os.getenv("TELEGRAM_PHONE")
SESSION  = "/home/agent/migration_agent/migration_agent_session"

async def create_session():
    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.connect()
    if not await client.is_user_authorized():
        await client.send_code_request(PHONE)
        code = input(f"Κωδικος SMS στο {PHONE}: ")
        try:
            await client.sign_in(PHONE, code)
        except SessionPasswordNeededError:
            pwd = input("2FA password: ")
            await client.sign_in(password=pwd)
    me = await client.get_me()
    print(f"OK: {me.first_name} (@{me.username})")
    await client.disconnect()

asyncio.run(create_session())
