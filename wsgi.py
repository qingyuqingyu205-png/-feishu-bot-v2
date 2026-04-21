#!/usr/bin/env python3
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))

# feishu_message_server.py 在 scripts/ 下
scripts_path = os.path.join(current_dir, 'scripts')
# tools/ 在 scripts/src/ 下
scripts_src_path = os.path.join(current_dir, 'scripts', 'src')

sys.path.insert(0, scripts_src_path)
sys.path.insert(0, scripts_path)

from feishu_message_server import app

application = app

if __name__ == '__main__':
    application.run(host='0.0.0.0', port=8080)
