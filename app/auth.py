from app.database import SessionLocal
from app.models import User
import bcrypt

def auth_user(u, p):
    s = SessionLocal()
    try:
        user = s.query(User).filter(User.username == u).first()
        if user and bcrypt.checkpw(p.encode(), user.password_hash.encode()):
            return user
    except Exception as e:
        pass
    finally:
        s.close()
    return None

def register_user_secure(u, f, p, role, code, t_id, d_id, m_type):
    # استكمال الكود هنا مع إضافة خاصية التسجيل
