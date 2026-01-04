from fpdf import FPDF
import arabic_reshaper
from bidi.algorithm import get_display
import os
import requests

# التأكد من وجود خط اللغة العربية
def ensure_font_exists():
    font_path = "Amiri-Regular.ttf"
    if not os.path.exists(font_path):
        try:
            url = "https://github.com/google/fonts/raw/main/ofl/amiri/Amiri-Regular.ttf"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                with open(font_path, "wb") as f:
                    f.write(response.content)
                return font_path
            else:
                return None
        except:
            return None
    return font_path

# معالجة النص العربي لـ FPDF
def process_text_for_pdf(text):
    """معالجة النص العربي لـ FPDF"""
    if not text: return ""
    text = str(text) 
    try:
        reshaped_text = arabic_reshaper.reshape(text)
        bidi_text = get_display(reshaped_text)
        return bidi_text
    except:
        return text

# فئة PDF لإنشاء ملفات PDF
class PDF(FPDF):
    def header(self):
        pass
    
    def footer(self):
        self.set_y(-15)
        # نستخدم Amiri دائماً في الفوتر
        if 'Amiri' in self.font_files:
            self.set_font('Amiri', '', 8)
        else:
            self.set_font('helvetica', '', 8)
        self.cell(0, 10, f'Page {self.page_no()}', align='C')

# دالة لإنشاء السيرة الذاتية (CV) بصيغة PDF
def generate_cv_pdf(user, df_works):
    font_path = ensure_font_exists()
    
    if not font_path:
        st.error("فشل تحميل خط اللغة العربية. سيتم استخدام الخط الافتراضي.")
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("helvetica", '', 12)
        pdf.cell(0, 10, "Arabic font not loaded.", ln=True)
        return bytes(pdf.output())

    pdf = FPDF()
    # تفعيل الفاصل التلقائي
    pdf.set_auto_page_break(auto=True, margin=15) 
    
    pdf.add_font('Amiri', '', font_path)
    pdf.add_page()
    
    # --- الرأس ---
    pdf.set_font("Amiri", '', 18)
    title = process_text_for_pdf(f"السيرة الذاتية الأكاديمية: {user.full_name}")
    pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.ln(5)

    pdf.set_font("Amiri", '', 11)
    role_str = MEMBER_TYPES.get(user.member_type, user.role)
    u_role = role_str if role_str else "غير محدد"
    u_team = user.team.name if user.team else (user.department.name_ar if user.department else 'غير محدد')

    role_text = process_text_for_pdf(f"الصفة: {u_role}")
    team_text = process_text_for_pdf(f"الهيكل: {u_team}")
    
    pdf.cell(0, 6, role_text, new_x="LMARGIN", new_y="NEXT", align='R')
    pdf.cell(0, 6, team_text, new_x="LMARGIN", new_y="NEXT", align='R')
    pdf.ln(8)
    
    # --- عنوان القائمة ---
    pdf.set_font("Amiri", '', 14)
    header = process_text_for_pdf("قائمة الأنشطة والنتاجات العلمية")
    pdf.set_draw_color(150, 150, 150)
    pdf.cell(0, 10, header, new_x="LMARGIN", new_y="NEXT", align='R')
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)
    
    if not df_works.empty:
        # فرز البيانات: النوع، ثم السنة تنازلياً
        df_sorted = df_works.sort_values(by=['activity_type', 'year'], ascending=[True, False])
        
        current_type = None
        
        for index, row in df_sorted.iterrows():
            # طباعة العنوان فقط عند التغيير
            if row['activity_type'] != current_type:
                current_type = row['activity_type']
                
                if pdf.get_y() > 250: 
                    pdf.add_page()
                else: 
                    pdf.ln(3)
                
                pdf.set_font("Amiri", '', 13)
                pdf.set_text_color(30, 60, 140)
                type_title = process_text_for_pdf(f"• {current_type}")
                
                # ضبط X دائماً لليسار قبل الطباعة
                pdf.set_x(10)
                # w=190 (تقريباً عرض A4 ناقص الهوامش) لتجنب خطأ المساحة
                pdf.cell(190, 8, type_title, ln=True, align='R')
            
            # طباعة التفاصيل
            pdf.set_text_color(0, 0, 0)
            pdf.set_font("Amiri", '', 11)
            
            title_clean = str(row['title'])
            date_clean = str(row['publication_date'])
            full_text = f"- {title_clean} ({date_clean})"
            final_text = process_text_for_pdf(full_text)
            
            # ضبط X دائماً لليسار قبل الطباعة
            pdf.set_x(10) 
            # w=190 لضمان وجود مساحة كافية للالتفاف وعدم ظهور خطأ
            pdf.multi_cell(190, 6, final_text, align='R')
            
    else:
        pdf.set_font("Amiri", '', 12)
        no_data = process_text_for_pdf("لا توجد أعمال مسجلة حتى الآن.")
        pdf.set_x(10)
        pdf.cell(190, 10, no_data, ln=True, align='R')
        
    return bytes(pdf.output())
