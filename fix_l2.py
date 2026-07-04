import sys, os
file_path = 'd:/project/Chips-II/app/blueprints/l2_registration.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

helper = """def get_valid_token():
    from flask import session
    raw_token = session.get("access_token", "")
    if isinstance(raw_token, dict):
        return raw_token.get("token", "") or raw_token.get("access_token", "")
    return str(raw_token).strip()
"""
if 'def get_valid_token()' not in content:
    content = content.replace('BACKEND = "http://127.0.0.1:8000/l2-registration"', 'BACKEND = "http://127.0.0.1:8000/l2-registration"\n\n' + helper)

content = content.replace('jwt_token = session.get("access_token")', 'jwt_token = get_valid_token()')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed tokens in l2 proxy')
