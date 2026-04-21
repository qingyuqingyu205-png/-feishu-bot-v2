#!/usr/bin/env python3
"""
飞书消息接收服务器

接收飞书推送的用户消息，传递给智能体处理，并将回复发送回飞书
"""

import sys
import os
import json
import re
import logging
from datetime import datetime
from collections import deque

from flask import Flask, request, jsonify

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools.feishu_bot_tool import get_bot_client
from tools.feishu_bitable_client import FeishuBitable

# 配置日志（输出到标准输出）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 消息去重缓存（最近1000条消息ID）
_PROCESSED_MESSAGES = deque(maxlen=1000)
_USER_MESSAGE_HISTORY = {}  # 时间窗口去重
_TIME_WINDOW = 2.0  # 2秒时间窗口

def is_duplicate_in_time_window(user_id: str, content: str) -> bool:
    """检查是否在时间窗口内有相同的消息"""
    import time
    if user_id not in _USER_MESSAGE_HISTORY:
        _USER_MESSAGE_HISTORY[user_id] = deque(maxlen=10)
        return False
    current_time = time.time()
    history = _USER_MESSAGE_HISTORY[user_id]
    for hist_content, hist_time in history:
        if hist_content == content and (current_time - hist_time) < _TIME_WINDOW:
            return True
    return False

def add_message_to_history(user_id: str, content: str):
    """添加消息到历史记录"""
    import time
    if user_id not in _USER_MESSAGE_HISTORY:
        _USER_MESSAGE_HISTORY[user_id] = deque(maxlen=10)
    _USER_MESSAGE_HISTORY[user_id].append((content, time.time()))

class FeishuMessageHandler:
    """飞书消息处理器"""

    def __init__(self):
        self.bot_client = get_bot_client()

    def handle_challenge(self, data: dict) -> dict:
        """处理飞书URL验证挑战"""
        challenge = data.get("challenge")
        logger.info(f"收到飞书URL验证挑战: {challenge}")
        return {"challenge": challenge}

    def handle_message_event(self, event: dict) -> bool:
        """处理用户消息事件"""
        try:
            sender = event.get("sender", {})
            user_id = sender.get("sender_id", {}).get("open_id", "")
            message = event.get("message", {})
            message_id = message.get("message_id", "")
            content = message.get("content", "")

            try:
                content_data = json.loads(content)
                user_text = content_data.get("text", "").strip()
            except json.JSONDecodeError:
                user_text = content.strip()

            if not user_text:
                return True

            if is_duplicate_in_time_window(user_id, user_text):
                return True

            if message_id and message_id in _PROCESSED_MESSAGES:
                return True

            logger.info(f"收到用户消息: user_id={user_id}, message={user_text}")

            if message_id:
                _PROCESSED_MESSAGES.append(message_id)
            add_message_to_history(user_id, user_text)

            response = self.call_agent(user_id, user_text, message_id)
            if response:
                self.send_reply(user_id, response)
                logger.info(f"已发送回复给用户: user_id={user_id}")

            return True

        except Exception as e:
            logger.error(f"处理消息事件失败: {str(e)}", exc_info=True)
            return False

    def call_agent(self, user_id: str, user_message: str, message_id: str) -> str:
        """调用智能体处理消息"""
        try:
            # 检测表格绑定链接
            table_link_pattern = r'https?://my\.feishu\.cn/base/[a-zA-Z0-9]+'
            if re.search(table_link_pattern, user_message):
                match = re.search(table_link_pattern, user_message)
                table_url = match.group(0)
                table_id_match = re.search(r'/base/([a-zA-Z0-9]+)', table_url)
                if not table_id_match:
                    return "无法识别表格链接，请检查链接是否正确喵~"
                
                app_token = table_id_match.group(1)
                logger.info(f"[表格绑定] user_id={user_id}, app_token={app_token}")

                # 保存绑定
                binding_file = "assets/user_binding.json"
                try:
                    os.makedirs("assets", exist_ok=True)
                    if os.path.exists(binding_file):
                        with open(binding_file, 'r', encoding='utf-8') as f:
                            bindings = json.load(f)
                    else:
                        bindings = {}
                except:
                    bindings = {}

                bindings[user_id] = app_token
                try:
                    with open(binding_file, 'w', encoding='utf-8') as f:
                        json.dump(bindings, f, ensure_ascii=False, indent=2)
                    return f"绑定成功喵~你的表格 ID：{app_token}\n\n接下来可以开始主线识别了喵~"
                except Exception as e:
                    logger.error(f"[表格绑定失败] {e}")
                    return "绑定失败，请重试喵~"

            # 导入智能体构建函数
            from agents.agent import build_agent
            from coze_coding_utils.runtime_ctx.context import new_context

            ctx = new_context(method="feishu_message")
            ctx.user_id = user_id
            ctx.message_id = message_id

            logger.info(f"正在创建智能体...")
            agent = build_agent(ctx)

            from langchain_core.messages import HumanMessage
            messages = [HumanMessage(content=user_message)]

            logger.info(f"正在调用智能体处理消息: {user_message}")
            response = agent.invoke(
                {"messages": messages},
                config={"configurable": {"thread_id": user_id}}
            )

            reply_messages = response.get("messages", [])
            if reply_messages:
                last_message = reply_messages[-1]
                if hasattr(last_message, 'content'):
                    return last_message.content
            return "抱歉，我暂时无法处理你的请求。"

        except Exception as e:
            logger.error(f"调用智能体失败: {str(e)}", exc_info=True)
            return f"处理请求时出错：{str(e)}"

    def send_reply(self, user_id: str, reply: str) -> bool:
        """发送回复给用户"""
        try:
            result = self.bot_client.send_text_message(
                receive_id=user_id,
                receive_id_type="open_id",
                content=reply
            )
            return result.get("code") == 0
        except Exception as e:
            logger.error(f"发送回复时出错: {str(e)}", exc_info=True)
            return False

message_handler = FeishuMessageHandler()

@app.route('/feishu/message', methods=['POST'])
def handle_feishu_message():
    """处理飞书消息推送"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"code": 1, "msg": "请求数据为空"}), 400

        logger.info(f"收到飞书消息推送: {json.dumps(data, ensure_ascii=False)}")

        # URL验证挑战
        if "challenge" in data:
            response = message_handler.handle_challenge(data)
            return jsonify(response)

        # 消息事件
        if "event" in data:
            event_type = data["event"].get("type", "")
            if event_type == "message":
                success = message_handler.handle_message_event(data["event"])
                if success:
                    return jsonify({"code": 0, "msg": "success"})
                return jsonify({"code": 1, "msg": "处理消息失败"}), 500
            return jsonify({"code": 0, "msg": "ignored"})

        return jsonify({"code": 1, "msg": "未知请求类型"}), 400

    except Exception as e:
        logger.error(f"处理飞书消息时出错: {str(e)}", exc_info=True)
        return jsonify({"code": 1, "msg": f"服务器错误: {str(e)}"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({
        "status": "ok",
        "service": "feishu_message_server",
        "timestamp": datetime.now().isoformat()
    })

def main():
    """主函数"""
    port = int(os.getenv("PORT", 8081))
    logger.info(f"🚀 飞书消息服务器启动，端口: {port}")
    app.run(host='0.0.0.0', port=port, threaded=True)

if __name__ == "__main__":
    main()
