from backend.database import SessionLocal, engine
from sqlalchemy import inspect, text

db = SessionLocal()
for t in inspect(engine).get_table_names():
    try:
        count = db.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar()
        print(f"{t}: {count}")
    except Exception as e:
        print(f"{t}: ERROR")
