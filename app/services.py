from app.database import SessionLocal
from app.models import Work, User
import bcrypt
import json
from datetime import date

def add_work_service(uid, title, details_json, atype, cls, date_obj, pts):
    s = SessionLocal()
    try:
        s.add(Work(user_id=uid, title=title, details=details_json, activity_type=atype, classification=cls, publication_date=date_obj, year=date_obj.year, points=pts))
        s.commit()
        return True
    except Exception as e:
        s.rollback()
        return False
    finally:
        s.close()

# استكمال باقي الخدمات مثل update_work_service, delete_work_service وغيرها

