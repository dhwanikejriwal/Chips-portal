import requests
import json

url = "http://127.0.0.1:8000/candidate_register/send-otp"
payload = {
    "email": "dhwanikejriwal07@gmail.com",
    "mobile": "8349857777"
}
try:
    r = requests.post(url, json=payload)
    print("Status:", r.status_code)
    print("Response:", r.text)
except Exception as e:
    print(e)
