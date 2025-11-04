from datetime import datetime
from fastapi import FastAPI
import uvicorn

from api.models import WebhookRequest
from api.services import process_webhook

app = FastAPI()

@app.post("/api/webhook")
def webhook(request: WebhookRequest):
    return process_webhook(request)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)