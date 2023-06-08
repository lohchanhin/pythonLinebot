from fastapi import FastAPI, Request, status, HTTPException
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, ImageMessage
import os
import openai as ai


# 配置 LINE 令牌和密钥
channel_access_token = os.getenv('CHANNEL_ACCESS_TOKEN')
channel_secret = os.getenv('CHANNEL_SECRET')

# 获取 OpenAI API 密钥
ai.api_key = os.getenv('OPENAI_API_KEY')

# 创建 LINE 客户端
line_bot_api = LineBotApi(channel_access_token)
handler = WebhookHandler(channel_secret)

app = FastAPI()

# 存储用户会话的对象
userConversations = {}

# 使用FastAPI创建Webhook回调函数
@app.post("/callback")
async def callback(request: Request):
    signature = request.headers["X-Line-Signature"]
    body = await request.body()

    try:
        handler.handle(body.decode(), signature)
    except InvalidSignatureError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid request"
        )

    return "OK"

# 处理用户发送的消息
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event: MessageEvent):
    print('halo')
    # 如果消息类型不是文本，则忽略
    if not isinstance(event.message, TextMessage):
        return
    
    text = event.message.text
    user_id = event.source.user_id

    # 如果不存在该用户的对话，为其创建一个
    if user_id not in userConversations:
        userConversations[user_id] = [
            {"role": "system", "content": '你是人工智能助理'}
        ]

    # 将用户消息添加到会话中
    userConversations[user_id].append({"role": "user", "content": text + '回答字數限制在1000以內'})

    # 如果会话长度超过 4 条消息，则删除最早的一条
    if len(userConversations[user_id]) > 4:
        userConversations[user_id].pop(0)

    # 使用 OpenAI API 获取回复
    openai_response =  ai.ChatCompletion.create(
        model="gpt-4",
        messages=userConversations[user_id]
    )

    # 获取助手回复的文本
    assistant_reply = openai_response['choices'][0]['message']['content']

    # 将助手回复添加到会话中
    userConversations[user_id].append({"role": "assistant", "content": assistant_reply})

    # 使用 LINE API 回复用户
    line_bot_api.reply_message(event.replyToken, TextSendMessage(text=assistant_reply))



