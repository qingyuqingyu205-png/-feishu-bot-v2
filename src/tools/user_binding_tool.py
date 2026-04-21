from langchain.tools import tool
from coze_coding_utils.log.write_log import request_context
from coze_coding_utils.runtime_ctx.context import new_context
import re
import json
import os

BINDING_FILE = "/workspace/projects/assets/user_binding.json"

def _load_bindings():
    """加载用户绑定数据"""
    if os.path.exists(BINDING_FILE):
        with open(BINDING_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def _save_bindings(bindings):
    """保存用户绑定数据"""
    with open(BINDING_FILE, 'w', encoding='utf-8') as f:
        json.dump(bindings, f, ensure_ascii=False, indent=2)

def _extract_table_id_from_url(url: str) -> str:
    match = re.search(r'/base/([a-zA-Z0-9]+)', url)
    if match:
        return match.group(1)
    return ""

@tool
def bind_user_table(url: str) -> str:
    """
    绑定用户的飞书多维表格
    
    Args:
        url: 飞书多维表格链接
    
    Returns:
        绑定结果信息
    """
    ctx = request_context.get() or new_context(method="bind_user_table")
    user_id = getattr(ctx, 'user_id', None) if ctx else None
    if not user_id:
        return "无法获取用户信息"
    
    table_id = _extract_table_id_from_url(url)
    if not table_id:
        return "无效的表格链接"
    
    bindings = _load_bindings()
    bindings[user_id] = table_id
    _save_bindings(bindings)
    
    return f"成功绑定表格：{table_id}"
