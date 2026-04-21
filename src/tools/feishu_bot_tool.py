import requests
import json
import time

FEISHU_APP_ID = "cli_a9693e0b4ef89cb5"
FEISHU_APP_SECRET = "2QrjiXLyXpEdNHflfbkFBcuK2ohHCLxo"
FEISHU_API_BASE = "https://open.feishu.cn/open-apis"

class FeishuBotClient:
    def __init__(self):
        self.app_id = FEISHU_APP_ID
        self.app_secret = FEISHU_APP_SECRET
        self.base_url = FEISHU_API_BASE
        self._tenant_access_token = None
        self._token_expire_time = 0

    def get_tenant_access_token(self) -> str:
        if self._tenant_access_token and time.time() < self._token_expire_time:
            return self._tenant_access_token

        url = f"{self.base_url}/auth/v3/tenant_access_token/internal"
        payload = {"app_id": self.app_id, "app_secret": self.app_secret}

        try:
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()

            if data.get("code") != 0:
                raise Exception(f"获取 tenant_access_token 失败: {data}")

            self._tenant_access_token = data.get("tenant_access_token")
            self._token_expire_time = time.time() + 7200 - 300
            return self._tenant_access_token
        except Exception as e:
            raise Exception(f"获取飞书 token 失败: {str(e)}")

    def send_text_message(self, receive_id: str, receive_id_type: str = "open_id", content: str = "") -> dict:
        token = self.get_tenant_access_token()
        url = f"{self.base_url}/im/v1/messages?receive_id_type={receive_id_type}"

        payload = {
            "msg_type": "text",
            "receive_id": receive_id,
            "content": json.dumps({"text": content})
        }

        try:
            response = requests.post(
                url,
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise Exception(f"发送飞书消息失败: {str(e)}")

_bot_client = None

def get_bot_client():
    global _bot_client
    if _bot_client is None:
        _bot_client = FeishuBotClient()
    return _bot_client
