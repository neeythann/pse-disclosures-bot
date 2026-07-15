import os

if not os.environ.get("WEBHOOK_URL"):
    os.environ["WEBHOOK_URL"] = "https://discord.com/api/webhooks/test"
