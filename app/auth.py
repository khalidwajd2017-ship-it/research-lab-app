from app.database import SessionLocal
from app.models import User
import bcrypt

# مصادقة المستخدم
def auth_user(u, p):
    s = SessionLocal()
    try:
        # البحث عن المستخدم بناءً على اسم المستخدم
        user = s.query(User).filter(User.username == u).first()
        # التحقق من كلمة المرور باستخدام bcrypt
        if user and bcrypt.checkpw(p.encode(), user.password_hash.encode()):
            return user
    except Exception as e:
        pass
    finally:
        s.close()
    return None

# تسجيل مستخدم جديد
def register_user_secure(u, f, p, role, code, t_id, d_id, m_type):
    # التحقق من كود التفعيل
    if code != ACTIVATION_CODES.get(role):
        return False, "⛔ كود التفعيل غير صحيح!"
    
    s = SessionLocal()
    try:
        # التحقق إذا كان اسم المستخدم موجودًا بالفعل
        if s.query(User).filter(User.username == u).first():
            return False, "⚠️ اسم المستخدم موجود"
        
        # تشفير كلمة المرور
        h = bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
        
        # إضافة المستخدم الجديد إلى قاعدة البيانات
        s.add(User(username=u, full_name=f, password_hash=h, role=role, team_id=t_id, department_id=d_id, member_type=m_type))
        s.commit()
        return True, "✅ تم الإنشاء"
    
    except Exception as e:
        s.rollback()
        return False, f"خطأ: {str(e)}"
    finally:
        s.close()

# تسجيل مستخدم يدويًا من قبل المدير أو رئيس القسم
def add_user_manual(u, f, p, role, t_id, d_id, m_type):
    s = SessionLocal()
    try:
        # التحقق إذا كان اسم المستخدم موجودًا بالفعل
        if s.query(User).filter(User.username == u).first():
            return False, "⚠️ اسم المستخدم موجود مسبقاً"
        
        # تشفير كلمة المرور
        h = bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
        
        # إضافة المستخدم الجديد إلى قاعدة البيانات
        s.add(User(username=u, full_name=f, password_hash=h, role=role, team_id=t_id, department_id=d_id, member_type=m_type))
        s.commit()
        return True, "✅ تمت الإضافة"
    
    except Exception as e:
        s.rollback()
        return False, "خطأ في إضافة المستخدم"
    finally:
        s.close()
