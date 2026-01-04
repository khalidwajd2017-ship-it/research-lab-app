from app.database import SessionLocal
from app.models import Work, User
import bcrypt
import json
from datetime import date

# إضافة عمل (Work) جديد
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

# تحديث العمل (Work) بناءً على ID
def update_work_service(wid, title, date_obj):
    s = SessionLocal()
    try:
        w = s.query(Work).filter(Work.id == wid).first()
        w.title = title
        w.publication_date = date_obj
        w.year = date_obj.year
        s.commit()
        return True
    except Exception as e:
        s.rollback()
        return False
    finally:
        s.close()

# حذف العمل (Work) بناءً على ID
def delete_work_service(wid):
    s = SessionLocal()
    try:
        s.query(Work).filter(Work.id == wid).delete()
        s.commit()
        return True
    except Exception as e:
        s.rollback()
        return False
    finally:
        s.close()

# تغيير كلمة المرور للمستخدم بناءً على ID
def change_password(uid, new_p):
    s = SessionLocal()
    try:
        user = s.query(User).filter(User.id == uid).first()
        user.password_hash = bcrypt.hashpw(new_p.encode(), bcrypt.gensalt()).decode()
        s.commit()
        return True
    except Exception as e:
        s.rollback()
        return False
    finally:
        s.close()

# استعلام البيانات الذكية (smart data) بناءً على الدور
def get_smart_data(user):
    base_q = """
    SELECT 
        w.id, w.user_id, w.title, w.activity_type, w.publication_date, w.year, w.points, w.classification, w.details,
        u.full_name as researcher, 
        t.name as team, 
        d.name_ar as department
    FROM works w
    JOIN users u ON w.user_id = u.id
    LEFT JOIN teams t ON u.team_id = t.id
    LEFT JOIN departments d ON u.department_id = d.id 
    """
    try:
        # استعلام البيانات من قاعدة البيانات
        df = pd.read_sql(base_q, engine)
        df['department'] = df['department'].fillna('غير محدد')
        df['team'] = df['team'].fillna('غير محدد')
        df['activity_type'] = df['activity_type'].fillna('غير محدد')
        df['publication_date'] = pd.to_datetime(df['publication_date']).dt.date
        
        if df.empty: 
            return df
        if user.role == 'admin': 
            return df
        elif user.role == 'dept_head': 
            if user.department: 
                return df[df['department'] == user.department.name_ar]
            return pd.DataFrame()
        elif user.role == 'leader': 
            if user.team: 
                return df[df['team'] == user.team.name]
            return pd.DataFrame()
        else: 
            return df[df['user_id'] == user.id]
    except Exception as e: 
        return pd.DataFrame()

# تحويل البيانات إلى تنسيق Excel
def to_excel(df):
    try:
        output = io.BytesIO()
        export_df = df.copy()
        if 'details' in export_df.columns:
            export_df['تفاصيل'] = export_df['details'].apply(lambda x: " | ".join([f"{k}:{v}" for k,v in json.loads(x).items() if v]) if x else "")
        cols_map = {'title': 'العنوان', 'activity_type': 'النوع', 'publication_date': 'التاريخ', 'points': 'النقاط', 'researcher': 'الباحث', 'team': 'الفرقة'}
        export_df = export_df.rename(columns=cols_map)
        final_cols = [c for c in cols_map.values() if c in export_df.columns] + ['تفاصيل']
        export_df = export_df[final_cols] if not export_df.empty else export_df
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            export_df.to_excel(writer, index=False, sheet_name='التقرير')
        return output.getvalue()
    except Exception as e:
        return None
