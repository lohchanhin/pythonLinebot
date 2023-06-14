from fastapi import FastAPI, Request, status, HTTPException
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os
import openai as ai
import requests

# 獲取 LINE 密鑰
channel_access_token = os.getenv('CHANNEL_ACCESS_TOKEN')
channel_secret = os.getenv('CHANNEL_SECRET')

# 創建 LINE 客戶端
line_bot_api = LineBotApi(channel_access_token)
handler = WebhookHandler(channel_secret)

app = FastAPI()

# 存儲用戶會話的對象
user_conversations = {}

def get_current_weather(location, units="metric"):
    """Get the current weather in a given location"""
    API_KEY = os.getenv('WEATHER_API_KEY')  # Get your API key from environment variables
    response = requests.get(
        f"http://api.openweathermap.org/data/2.5/weather?q={location}&appid={API_KEY}&units={units}"
    )
    weather_info = response.json()
    return {
        "location": location,
        "temperature": weather_info["main"]["temp"],
        "description": weather_info["weather"][0]["description"],
        "units": units,
    }


# 創建回調函數
@app.post("/callback")
async def callback(request: Request):
    # 獲取請求簽名
    signature = request.headers["X-Line-Signature"]

    # 獲取請求內容
    body = await request.body()

    try:
        # 驗證簽名和處理請求
        handler.handle(body.decode(), signature)
    except InvalidSignatureError:
        # 如果簽名不正確，則返回 HTTP 403 錯誤
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid request"
        )

    return "OK"

# 處理用戶發送的消息
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event: MessageEvent):
    # 如果消息類型不是文本，則忽略
    if not isinstance(event.message, TextMessage):
        return

    # 進行自然語言處理並回復用戶
    text = event.message.text
    user_id = event.source.user_id

    # 如果不存在該用戶的對話，為其創建一個
    if user_id not in user_conversations:
        user_conversations[user_id] = [
            {"role": "system", "content": '你是人工智能助理'}
        ]

    # 將用戶消息添加到會話中
    user_conversations[user_id].append({"role": "user", "content": text + '回答字數限制在1000以內'})

    # 如果會話長度超過 4 條消息，則刪除最早的一條
    if len(user_conversations[user_id]) > 4:
        user_conversations[user_id].pop(0)

    # 獲取 OpenAI API 密鑰
    openai_api_key = os.getenv('OPENAI_API_KEY')

    # 使用 OpenAI API 獲取回復
    ai.api_key = openai_api_key
    openai_response =  ai.ChatCompletion.create(
        model="gpt-4-0613",
        messages=user_conversations[user_id],
        functions=[
            {
                "name": "get_current_weather",
                "description": "Get the current weather in a given location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The city and state, e.g. San Francisco, CA",
                        },
                        "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                    },
                    "required": ["location"],
                },
            }
        ],
        function_call="auto",
    )
    # Step 2, check if the model wants to call a function
    message = openai_response["choices"][0]["message"]
    if "function_call" in message:
        function_name = message["function_call"]["name"]
        function_params = message["function_call"].get("params", {}) # Use the .get() method to avoid KeyError


        # Step 3, call the function
        function_response = None
        if function_name == "get_current_weather":
            function_response = get_current_weather(**function_params)

        # If other functions are defined, call them here
        # ...

        # Step 4, send model the info on the function call and function response
        user_conversations[user_id].append({
            "role": "function",
            "name": function_name,
            "content": function_response,
        })

    


    # 獲取助手回復的文本
    assistant_reply = openai_response['choices'][0]['message']['content']

    # 將助手回復添加到會話中
    user_conversations[user_id].append({"role": "assistant", "content": assistant_reply})

    # 使用 LINE API 回復用戶
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=assistant_reply))
