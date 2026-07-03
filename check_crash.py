import sys
import traceback

try:
    from backend.main import app
    print("App loaded successfully")
except Exception as e:
    with open("crash_log.txt", "w") as f:
        f.write(traceback.format_exc())
    print("App crashed. Check crash_log.txt")
