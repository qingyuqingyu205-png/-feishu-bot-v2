import requests
from coze_workload_identity import Client

client = Client()

def get_access_token() -> str:
    access_token = client.get_integration_credential("integration-feishu-base")
    return access_token

class FeishuBitable:
    def __init__(self, base_url: str = "https://open.larkoffice.com/open-apis"):
        self.base_url = base_url.rstrip("/")
        self.access_token = get_access_token()

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=utf-8",
        }

    def _request(self, method: str, path: str, json: dict = None) -> dict:
        url = f"{self.base_url}{path}"
        resp = requests.request(method, url, headers=self._headers(), json=json)
        return resp.json()
