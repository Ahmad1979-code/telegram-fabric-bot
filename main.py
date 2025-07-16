from flask import Flask, request
import requests
import os
import json

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

# Google Sheets API
import gspread
from oauth2client.service_account import ServiceAccountCredentials

scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds_json = json.loads(os.getenv("GOOGLE_CREDS"))  # из переменной окружения
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
client = gspread.authorize(creds)

def extract_sizes(text):
    import re
    return re.findall(r'(\d{2,3})\s*[xх*]\s*(\d{2,3})', text)

def extract_multiplier(text):
    import re
    match = re.search(r'х\s*(\d+)', text, re.I)
    return int(match.group(1)) if match else 1

def extract_sheet_name(text):
    import re
    match = re.match(r'^(.+?)\s*\d{2,3}[xх*]', text, re.I)
    return match.group(1).strip() if match else ''

@app.route("/", methods=["POST"])
def telegram_webhook():
    data = request.json
    if "message" not in data:
        return "ok"

    message = data["message"]
    chat_id = message["chat"]["id"]
    text = message.get("text", "")

    sheet_name = extract_sheet_name(text)
    sizes = extract_sizes(text)
    multiplier = extract_multiplier(text)

    if not sheet_name or not sizes:
        send_message(chat_id, "❌ Не удалось определить лист или размеры")
        return "ok"

    try:
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(sheet_name)
        data = sheet.get_all_values()
        width_row = data[0]
        height_col = [row[0] for row in data]

        total = 0
        details = []

        for w_raw, h_raw in sizes:
            width = round_up(float(w_raw) / 100, 0.1)
            height = round_up(float(h_raw) / 100, 0.1)

            try:
                w_idx = width_row.index(str(width).replace(".", ","))
                h_idx = height_col.index(str(height).replace(".", ","))

                price = float(data[h_idx][w_idx])
                total += price
                details.append(f"• {w_raw}x{h_raw} → {price:.2f}")
            except:
                details.append(f"• {w_raw}x{h_raw} → ❌ не найдено")

        total_sum = total * multiplier
        response = f"📄 Лист: {sheet_name}\n" + "\n".join(details) + f"\n\n💰 Общая стоимость: {total_sum:.2f}₽ (x{multiplier})"
        send_message(chat_id, response)
    except Exception as e:
        send_message(chat_id, f"❌ Ошибка: {str(e)}")

    return "ok"

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text})

def round_up(value, step):
    import math
    return math.ceil(value / step) * step

if __name__ == "__main__":
    app.run()

      
