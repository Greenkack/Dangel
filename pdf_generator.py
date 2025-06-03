"""
Datei: pdf_generator.py
Zweck: Erzeugt Angebots-PDFs für die Solar-App.
Autor: Gemini Ultra (maximale KI-Performance)
Datum: 2025-06-03
"""
# pdf_generator.py

from __future__ import annotations

import base64
import io
import math
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, Callable
import os

_REPORTLAB_AVAILABLE = False
_PYPDF_AVAILABLE = False

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm, mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
    from reportlab.platypus import (Frame, Image, PageBreak, PageTemplate,
        Paragraph, SimpleDocTemplate, Spacer, Table,
        TableStyle, Flowable, KeepInFrame)
    from reportlab.lib import pagesizes
    _REPORTLAB_AVAILABLE = True
except ImportError:
    pass
except Exception as e_reportlab_import:
    pass

try:
    from pypdf import PdfReader, PdfWriter
    _PYPDF_AVAILABLE = True
except ImportError:
    try:
        from PyPDF2 import PdfReader, PdfWriter
        _PYPDF_AVAILABLE = True
    except ImportError:
        class PdfReader: # type: ignore
            def __init__(self, *args, **kwargs): pass
            @property
            def pages(self): return []
        class PdfWriter: # type: ignore
            def __init__(self, *args, **kwargs): pass
            def add_page(self, page): pass
            def write(self, stream): pass
        _PYPDF_AVAILABLE = False
except Exception as e_pypdf_import:
    class PdfReader: # type: ignore
        def __init__(self, *args, **kwargs): pass
        @property
        def pages(self): return []
    class PdfWriter: # type: ignore
        def __init__(self, *args, **kwargs): pass
        def add_page(self, page): pass
        def write(self, stream): pass
    _PYPDF_AVAILABLE = False

_PDF_GENERATOR_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_MAIN_APP_BASE_DIR = os.path.dirname(_PDF_GENERATOR_BASE_DIR)
PRODUCT_DATASHEETS_BASE_DIR_PDF_GEN = os.path.join(_MAIN_APP_BASE_DIR, "data", "product_datasheets")
COMPANY_DOCS_BASE_DIR_PDF_GEN = os.path.join(_MAIN_APP_BASE_DIR, "data", "company_docs")


def get_text(texts_dict: Dict[str, str], key: str, fallback_text_value: Optional[str] = None) -> str:
    if not isinstance(texts_dict, dict): return fallback_text_value if fallback_text_value is not None else key
    if fallback_text_value is None: fallback_text_value = key.replace("_", " ").title() + " (PDF-Text fehlt)"
    retrieved = texts_dict.get(key, fallback_text_value)
    return str(retrieved)

def format_kpi_value(value: Any, unit: str = "", na_text_key: str = "not_applicable_short", precision: int = 2, texts_dict: Optional[Dict[str,str]] = None) -> str:
    current_texts = texts_dict if texts_dict is not None else {}
    na_text = get_text(current_texts, na_text_key, "k.A.")
    if value is None or (isinstance(value, (float, int)) and math.isnan(value)): return na_text
    if isinstance(value, str) and value == na_text: return value
    if isinstance(value, str):
        try:
            cleaned_value_str = value
            if '.' in value and ',' in value:
                 if value.rfind('.') > value.rfind(','): cleaned_value_str = value.replace(',', '')
                 elif value.rfind(',') > value.rfind('.'): cleaned_value_str = value.replace('.', '')
            cleaned_value_str = cleaned_value_str.replace(',', '.')
            value = float(cleaned_value_str)
        except ValueError: return value

    if isinstance(value, (int, float)):
        if math.isinf(value): return get_text(current_texts, "value_infinite", "Nicht berechenbar")
        if unit == "Jahre": return get_text(current_texts, "years_format_string_pdf", "{val:.1f} Jahre").format(val=value)
        
        formatted_num_en = f"{value:,.{precision}f}"
        formatted_num_de = formatted_num_en.replace(",", "#TEMP#").replace(".", ",").replace("#TEMP#", ".")
        return f"{formatted_num_de} {unit}".strip()
    return str(value)

STYLES: Any = {}
FONT_NORMAL = "Helvetica"; FONT_BOLD = "Helvetica-Bold"; FONT_ITALIC = "Helvetica-Oblique"
PRIMARY_COLOR_HEX = "#003366"
SECONDARY_COLOR_HEX = "#4F81BD"
TEXT_COLOR_HEX = "#333333"

if _REPORTLAB_AVAILABLE: # Definiere Styles nur wenn ReportLab verfügbar ist
    STYLES = getSampleStyleSheet()
    STYLES.add(ParagraphStyle(name='NormalLeft', alignment=TA_LEFT, fontName=FONT_NORMAL, fontSize=10, leading=12, textColor=colors.HexColor(TEXT_COLOR_HEX)))
    STYLES.add(ParagraphStyle(name='NormalRight', alignment=TA_RIGHT, fontName=FONT_NORMAL, fontSize=10, leading=12, textColor=colors.HexColor(TEXT_COLOR_HEX)))
    STYLES.add(ParagraphStyle(name='NormalCenter', alignment=TA_CENTER, fontName=FONT_NORMAL, fontSize=10, leading=12, textColor=colors.HexColor(TEXT_COLOR_HEX)))
    STYLES.add(ParagraphStyle(name='Footer', parent=STYLES['NormalCenter'], fontName=FONT_ITALIC, fontSize=8, textColor=colors.grey))
    STYLES.add(ParagraphStyle(name='OfferTitle', parent=STYLES['h1'], fontName=FONT_BOLD, fontSize=18, alignment=TA_CENTER, spaceBefore=1*cm, spaceAfter=0.8*cm, textColor=colors.HexColor(PRIMARY_COLOR_HEX)))
    STYLES.add(ParagraphStyle(name='SectionTitle', parent=STYLES['h2'], fontName=FONT_BOLD, fontSize=14, spaceBefore=0.8*cm, spaceAfter=0.4*cm, keepWithNext=1, textColor=colors.HexColor(PRIMARY_COLOR_HEX)))
    STYLES.add(ParagraphStyle(name='SubSectionTitle', parent=STYLES['h3'], fontName=FONT_BOLD, fontSize=12, spaceBefore=0.6*cm, spaceAfter=0.3*cm, keepWithNext=1, textColor=colors.HexColor(SECONDARY_COLOR_HEX)))
    STYLES.add(ParagraphStyle(name='ComponentTitle', parent=STYLES['SubSectionTitle'], fontSize=11, spaceBefore=0.4*cm, spaceAfter=0.1*cm, alignment=TA_LEFT, textColor=colors.HexColor(TEXT_COLOR_HEX)))
    STYLES.add(ParagraphStyle(name='CompanyInfoDeckblatt', parent=STYLES['NormalCenter'], fontName=FONT_NORMAL, fontSize=9, leading=11, spaceAfter=0.5*cm, textColor=colors.HexColor(TEXT_COLOR_HEX)))
    STYLES.add(ParagraphStyle(name='CoverLetter', parent=STYLES['NormalLeft'], fontSize=11, leading=14, spaceBefore=0.5*cm, spaceAfter=0.5*cm, alignment=TA_JUSTIFY, firstLineIndent=0, leftIndent=0, rightIndent=0, textColor=colors.HexColor(TEXT_COLOR_HEX)))
    STYLES.add(ParagraphStyle(name='CustomerAddress', parent=STYLES['NormalLeft'], fontSize=10, leading=12, spaceBefore=0.5*cm, spaceAfter=0.8*cm, textColor=colors.HexColor(TEXT_COLOR_HEX)))
    STYLES.add(ParagraphStyle(name='TableText', parent=STYLES['NormalLeft'], fontName=FONT_NORMAL, fontSize=9, leading=11, textColor=colors.HexColor(TEXT_COLOR_HEX)))
    STYLES.add(ParagraphStyle(name='TableTextSmall', parent=STYLES['NormalLeft'], fontName=FONT_NORMAL, fontSize=8, leading=10, textColor=colors.HexColor(TEXT_COLOR_HEX)))
    STYLES.add(ParagraphStyle(name='TableNumber', parent=STYLES['NormalRight'], fontName=FONT_NORMAL, fontSize=9, leading=11, textColor=colors.HexColor(TEXT_COLOR_HEX)))
    STYLES.add(ParagraphStyle(name='TableLabel', parent=STYLES['NormalLeft'], fontName=FONT_BOLD, fontSize=9, leading=11, textColor=colors.HexColor(TEXT_COLOR_HEX)))
    STYLES.add(ParagraphStyle(name='TableHeader', parent=STYLES['NormalCenter'], fontName=FONT_BOLD, fontSize=9, leading=11, textColor=colors.whitesmoke, backColor=colors.HexColor(SECONDARY_COLOR_HEX)))
    STYLES.add(ParagraphStyle(name='TableBoldRight', parent=STYLES['NormalRight'], fontName=FONT_BOLD, fontSize=9, leading=11, textColor=colors.HexColor(TEXT_COLOR_HEX)))
    STYLES.add(ParagraphStyle(name='ImageCaption', parent=STYLES['NormalCenter'], fontName=FONT_ITALIC, fontSize=8, spaceBefore=0.1*cm, textColor=colors.grey))
    STYLES.add(ParagraphStyle(name='ChartTitle', parent=STYLES['SubSectionTitle'], alignment=TA_CENTER, spaceBefore=0.6*cm, spaceAfter=0.2*cm, fontSize=11, textColor=colors.HexColor(TEXT_COLOR_HEX)))
    STYLES.add(ParagraphStyle(name='ChapterHeader', parent=STYLES['NormalRight'], fontName=FONT_NORMAL, fontSize=9, textColor=colors.grey, alignment=TA_RIGHT))
    TABLE_STYLE_DEFAULT = TableStyle([('BACKGROUND', (0,0), (0,-1), colors.lightgrey), ('TEXTCOLOR',(0,0),(-1,-1),colors.HexColor(TEXT_COLOR_HEX)),('FONTNAME',(0,0),(0,-1),FONT_BOLD),('ALIGN',(0,0),(0,-1),'LEFT'),('ALIGN',(1,0),(1,-1),'RIGHT'),('GRID',(0,0),(-1,-1),0.5,colors.grey),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),3*mm),('RIGHTPADDING',(0,0),(-1,-1),3*mm),('TOPPADDING',(0,0),(-1,-1),2*mm),('BOTTOMPADDING',(0,0),(-1,-1),2*mm)])
    DATA_TABLE_STYLE = TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor(SECONDARY_COLOR_HEX)),('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),('FONTNAME',(0,0),(-1,0),FONT_BOLD),('ALIGN',(0,0),(-1,0),'CENTER'),('GRID',(0,0),(-1,-1),0.5,colors.grey),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('FONTNAME',(0,1),(-1,-1),FONT_NORMAL),('ALIGN',(0,1),(0,-1),'LEFT'),('ALIGN',(1,1),(-1,-1),'RIGHT'),('LEFTPADDING',(0,0),(-1,-1),2*mm),('RIGHTPADDING',(0,0),(-1,-1),2*mm),('TOPPADDING',(0,0),(-1,-1),1.5*mm),('BOTTOMPADDING',(0,0),(-1,-1),1.5*mm), ('TEXTCOLOR',(1,1),(-1,-1),colors.HexColor(TEXT_COLOR_HEX))])
    PRODUCT_TABLE_STYLE = TableStyle([('TEXTCOLOR',(0,0),(-1,-1),colors.HexColor(TEXT_COLOR_HEX)),('FONTNAME',(0,0),(0,-1),FONT_BOLD),('ALIGN',(0,0),(0,-1),'LEFT'),('FONTNAME',(1,0),(1,-1),FONT_NORMAL),('ALIGN',(1,0),(1,-1),'LEFT'),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),2*mm),('RIGHTPADDING',(0,0),(-1,-1),2*mm),('TOPPADDING',(0,0),(-1,-1),1.5*mm),('BOTTOMPADDING',(0,0),(-1,-1),1.5*mm)])
    PRODUCT_MAIN_TABLE_STYLE = TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0)])

class PageNumCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        self._page_layout_callback = kwargs.pop('onPage_callback', None)
        self._callback_kwargs = kwargs.pop('callback_kwargs', {})
        super().__init__(*args, **kwargs)
        self._saved_page_states = []
        self.total_pages = 0 
        self.current_chapter_title_for_header = '' 
    def showPage(self): 
        self._saved_page_states.append(dict(self.__dict__))
        super().showPage()
    
    def save(self):
        self.total_pages = len(self._saved_page_states) 
        for state_idx, state in enumerate(self._saved_page_states):
            self.__dict__.update(state) 
            self._pageNumber = state_idx + 1 
            if self._page_layout_callback:
                self._page_layout_callback(canvas_obj=self, doc_template=self._doc, **self._callback_kwargs)
            # KORREKTUR: Der folgende super().showPage() Aufruf wurde entfernt, um Duplizierung zu verhindern.
            # Der page_layout_callback zeichnet Kopf/Fußzeile auf den Canvas. SimpleDocTemplate hat den Inhalt bereits gezeichnet.
        super().save() 


class SetCurrentChapterTitle(Flowable):
    def __init__(self, title): Flowable.__init__(self); self.title = title
    def wrap(self, availWidth, availHeight): return 0,0
    def draw(self):
        if hasattr(self, 'canv'): self.canv.current_chapter_title_for_header = self.title

def _update_styles_with_dynamic_colors(design_settings: Dict[str, str]):
    global PRIMARY_COLOR_HEX, SECONDARY_COLOR_HEX, STYLES, DATA_TABLE_STYLE
    if not _REPORTLAB_AVAILABLE: return

    PRIMARY_COLOR_HEX = design_settings.get('primary_color', '#003366')
    SECONDARY_COLOR_HEX = design_settings.get('secondary_color', '#4F81BD')
    
    STYLES['OfferTitle'].textColor = colors.HexColor(PRIMARY_COLOR_HEX)
    STYLES['SectionTitle'].textColor = colors.HexColor(PRIMARY_COLOR_HEX)
    STYLES['SubSectionTitle'].textColor = colors.HexColor(SECONDARY_COLOR_HEX)
    STYLES['TableHeader'].backColor = colors.HexColor(SECONDARY_COLOR_HEX) # Wird bereits für DATA_TABLE_STYLE verwendet
    
    # Aktualisiere DATA_TABLE_STYLE direkt mit den neuen Farben
    DATA_TABLE_STYLE = TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor(SECONDARY_COLOR_HEX)), 
        ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
        ('FONTNAME',(0,0),(-1,0),FONT_BOLD),
        ('ALIGN',(0,0),(-1,0),'CENTER'),
        ('GRID',(0,0),(-1,-1),0.5,colors.grey),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('FONTNAME',(0,1),(-1,-1),FONT_NORMAL),
        ('ALIGN',(0,1),(0,-1),'LEFT'),
        ('ALIGN',(1,1),(-1,-1),'RIGHT'),
        ('LEFTPADDING',(0,0),(-1,-1),2*mm),
        ('RIGHTPADDING',(0,0),(-1,-1),2*mm),
        ('TOPPADDING',(0,0),(-1,-1),1.5*mm),
        ('BOTTOMPADDING',(0,0),(-1,-1),1.5*mm), 
        ('TEXTCOLOR',(1,1),(-1,-1),colors.HexColor(TEXT_COLOR_HEX))
    ])


def _get_image_flowable(image_data_input: Optional[Union[str, bytes]], desired_width: float, texts: Dict[str, str], caption_text_key: Optional[str] = None, max_height: Optional[float] = None, align: str = 'CENTER') -> List[Any]:
    flowables: List[Any] = []
    if not _REPORTLAB_AVAILABLE: return flowables
    img_data_bytes: Optional[bytes] = None

    if isinstance(image_data_input, str) and image_data_input.strip().lower() not in ["", "none", "null", "nan"]:
        try:
            if image_data_input.startswith('data:image'): image_data_input = image_data_input.split(',', 1)[1]
            img_data_bytes = base64.b64decode(image_data_input)
        except Exception: img_data_bytes = None 
    elif isinstance(image_data_input, bytes): img_data_bytes = image_data_input
    
    if img_data_bytes:
        try:
            if not img_data_bytes: raise ValueError("Bilddaten sind leer nach Verarbeitung.")
            img_file_like = io.BytesIO(img_data_bytes)
            img_reader = ImageReader(img_file_like)
            iw, ih = img_reader.getSize()
            if iw <= 0 or ih <= 0: raise ValueError(f"Ungültige Bilddimensionen: w={iw}, h={ih}")
            aspect = ih / float(iw) if iw > 0 else 1.0
            img_h_calc = desired_width * aspect; img_w_final, img_h_final = desired_width, img_h_calc
            if max_height and img_h_calc > max_height: img_h_final = max_height; img_w_final = img_h_final / aspect if aspect > 0 else desired_width
            
            img = Image(io.BytesIO(img_data_bytes), width=img_w_final, height=img_h_final)
            img.hAlign = align.upper(); flowables.append(img)
            if caption_text_key:
                caption_text = get_text(texts, caption_text_key, "")
                if caption_text and not caption_text.startswith(caption_text_key) and not caption_text.endswith("(PDF-Text fehlt)"):
                    flowables.append(Spacer(1, 0.1*cm)); flowables.append(Paragraph(caption_text, STYLES['ImageCaption']))
        except Exception: 
            if caption_text_key :
                caption_text_fb = get_text(texts, caption_text_key, "")
                if caption_text_fb and not caption_text_fb.startswith(caption_text_key):
                     flowables.append(Paragraph(f"<i>({caption_text_fb}: {get_text(texts, 'image_not_available_pdf', 'Bild nicht verfügbar')})</i>", STYLES['ImageCaption']))
    elif caption_text_key:
        caption_text_fb = get_text(texts, caption_text_key, "")
        if caption_text_fb and not caption_text_fb.startswith(caption_text_key):
            flowables.append(Paragraph(f"<i>({caption_text_fb}: {get_text(texts, 'image_not_available_pdf', 'Bild nicht verfügbar')})</i>", STYLES['ImageCaption']))
    return flowables

def page_layout_handler(canvas_obj: canvas.Canvas, doc_template: SimpleDocTemplate, texts_ref: Dict[str, str], company_info_ref: Dict, company_logo_base64_ref: Optional[str], offer_number_ref: str, page_width_ref: float, page_height_ref: float, margin_left_ref: float, margin_right_ref: float, margin_top_ref: float, margin_bottom_ref: float, doc_width_ref: float, doc_height_ref: float):
    canvas_obj.saveState()
    current_chapter_title = getattr(canvas_obj, 'current_chapter_title_for_header', '')
    page_num = canvas_obj.getPageNumber()

    if company_logo_base64_ref and page_num > 1:
        try:
            logo_flowables_footer = _get_image_flowable(company_logo_base64_ref, 1.8*cm, texts_ref, max_height=1.0*cm, align='LEFT')
            if logo_flowables_footer and isinstance(logo_flowables_footer[0], Image):
                logo_img_footer: Image = logo_flowables_footer[0]
                logo_bytes_for_draw = base64.b64decode(company_logo_base64_ref.split(',',1)[1]) if ',' in company_logo_base64_ref and len(company_logo_base64_ref.split(',',1)) > 1 else base64.b64decode(company_logo_base64_ref)
                canvas_obj.drawImage(ImageReader(io.BytesIO(logo_bytes_for_draw)), margin_left_ref, margin_bottom_ref * 0.35, width=logo_img_footer.drawWidth, height=logo_img_footer.drawHeight, mask='auto', preserveAspectRatio=True)
        except Exception: 
            pass
    
    if current_chapter_title and page_num > 1:
        p_chapter = Paragraph(current_chapter_title, STYLES['ChapterHeader'])
        p_w, p_h = p_chapter.wrapOn(canvas_obj, doc_width_ref - (2.5*cm), margin_top_ref)
        p_chapter.drawOn(canvas_obj, page_width_ref - margin_right_ref - p_w, page_height_ref - margin_top_ref + 0.3*cm)

    if page_num > 1:
        page_info_text = get_text(texts_ref, "pdf_page_x_of_y", "Seite {current} von {total}").format(current=str(page_num), total=str(getattr(canvas_obj, 'total_pages', '??')))
        footer_text_fmt = get_text(texts_ref, "pdf_footer_text_format_simple", "Angebot {offer_no} | {date} | {page_info}")
        final_footer_text = footer_text_fmt.format(offer_no=offer_number_ref, date=datetime.now().strftime('%d.%m.%Y'), page_info=page_info_text)
        canvas_obj.setFont(FONT_ITALIC, 8); canvas_obj.drawRightString(page_width_ref - margin_right_ref, margin_bottom_ref * 0.45, final_footer_text)

    company_specific_footer_line = company_info_ref.get('pdf_footer_text', '')
    if company_specific_footer_line and page_num > 1:
        canvas_obj.setFont(FONT_NORMAL, 7); canvas_obj.drawCentredString(page_width_ref / 2.0, margin_bottom_ref * 0.75, company_specific_footer_line)

    canvas_obj.restoreState()

def _generate_complete_salutation_line(customer_data: Dict, texts: Dict[str, str]) -> str:
    salutation_value = customer_data.get("salutation") 
    title = customer_data.get("title", "")
    first_name = customer_data.get("first_name", "")
    last_name = customer_data.get("last_name", "")

    name_parts = [p for p in [title, first_name, last_name] if p and str(p).strip()]
    customer_full_name_for_salutation = " ".join(name_parts).strip()

    salutation_key_base = "salutation_polite"
    if isinstance(salutation_value, str):
        sl_lower = salutation_value.lower().strip()
        if sl_lower == "herr": salutation_key_base = "salutation_male_polite"
        elif sl_lower == "frau": salutation_key_base = "salutation_female_polite"
        elif sl_lower == "familie":
            fam_name = last_name if last_name and str(last_name).strip() else customer_data.get("company_name", get_text(texts, "family_default_name_pdf", "Familie"))
            return f"{get_text(texts, 'salutation_family_polite', 'Sehr geehrte Familie')} {str(fam_name).strip()},"
        elif sl_lower == "firma": 
            company_name_val = customer_data.get("company_name", "") or last_name 
            if company_name_val: return f"{get_text(texts, 'salutation_company_polite', 'Sehr geehrte Damen und Herren der Firma')} {str(company_name_val).strip()},"
            else: return get_text(texts, 'salutation_generic_fallback', 'Sehr geehrte Damen und Herren,')
    
    default_salutation_text = get_text(texts, salutation_key_base, "Sehr geehrte/r")
    
    if customer_full_name_for_salutation:
        return f"{default_salutation_text} {customer_full_name_for_salutation},"
    else: 
        return get_text(texts, 'salutation_generic_fallback', 'Sehr geehrte Damen und Herren,')


def _replace_placeholders(text_template: str, customer_data: Dict, company_info: Dict, offer_number: str, texts_dict: Dict[str, str], analysis_results_for_placeholder: Optional[Dict[str, Any]] = None) -> str:
    if text_template is None: text_template = ""
    processed_text = str(text_template)
    now_date_str = datetime.now().strftime('%d.%m.%Y')
    complete_salutation_line = _generate_complete_salutation_line(customer_data, texts_dict)

    ersatz_dict = {
        "[VollständigeAnrede]": complete_salutation_line,
        "[Ihr Name/Firmenname]": str(company_info.get("name", get_text(texts_dict, "company_name_default_placeholder_pdf", "Ihr Solarexperte"))),
        "[Angebotsnummer]": str(offer_number),
        "[Datum]": now_date_str,
        "[KundenNachname]": str(customer_data.get("last_name", "")),
        "[KundenVorname]": str(customer_data.get("first_name", "")),
        "[KundenAnredeFormell]": str(customer_data.get("salutation", "")),
        "[KundenTitel]": str(customer_data.get("title", "")),
        "[KundenStrasseNr]": f"{customer_data.get('address','')} {customer_data.get('house_number','',)}".strip(),
        "[KundenPLZOrt]": f"{customer_data.get('zip_code','')} {customer_data.get('city','',)}".strip(),
        "[KundenFirmenname]": str(customer_data.get("company_name", "")),
    }
    if analysis_results_for_placeholder and isinstance(analysis_results_for_placeholder, dict):
        anlage_kwp_val = analysis_results_for_placeholder.get('anlage_kwp')
        ersatz_dict["[AnlagenleistungkWp]"] = format_kpi_value(anlage_kwp_val, "kWp", texts_dict=texts_dict, na_text_key="value_not_calculated_short") if anlage_kwp_val is not None else get_text(texts_dict, "value_not_calculated_short", "k.B.")
        
        total_invest_brutto_val = analysis_results_for_placeholder.get('total_investment_brutto')
        ersatz_dict["[GesamtinvestitionBrutto]"] = format_kpi_value(total_invest_brutto_val, "€", texts_dict=texts_dict, na_text_key="value_not_calculated_short") if total_invest_brutto_val is not None else get_text(texts_dict, "value_not_calculated_short", "k.B.")

        annual_benefit_yr1_val = analysis_results_for_placeholder.get('annual_financial_benefit_year1')
        ersatz_dict["[FinanziellerVorteilJahr1]"] = format_kpi_value(annual_benefit_yr1_val, "€", texts_dict=texts_dict, na_text_key="value_not_calculated_short") if annual_benefit_yr1_val is not None else get_text(texts_dict, "value_not_calculated_short", "k.B.")

    for placeholder, value_repl in ersatz_dict.items():
        processed_text = processed_text.replace(placeholder, str(value_repl))
    return processed_text

def _get_next_offer_number(texts: Dict[str,str], load_admin_setting_func: Callable, save_admin_setting_func: Callable) -> str:
    try:
        current_suffix_obj = load_admin_setting_func('offer_number_suffix', 1000)
        current_suffix = int(str(current_suffix_obj)) if current_suffix_obj is not None else 1000
        next_suffix = current_suffix + 1
        save_admin_setting_func('offer_number_suffix', next_suffix)
        return f"AN{datetime.now().year}-{next_suffix:04d}"
    except Exception: 
        return f"AN{datetime.now().strftime('%Y%m%d-%H%M%S')}"

def _prepare_cost_table_for_pdf(analysis_results: Dict[str, Any], texts: Dict[str, str]) -> List[List[Any]]:
    cost_data_pdf = []
    cost_items_ordered_pdf = [
        ('base_matrix_price_netto', 'base_matrix_price_netto', True, 'TableText'),
        ('cost_modules_aufpreis_netto', 'cost_modules', True, 'TableText'),
        ('cost_inverter_aufpreis_netto', 'cost_inverter', True, 'TableText'),
        ('cost_storage_aufpreis_product_db_netto', 'cost_storage', True, 'TableText'),
        ('total_optional_components_cost_netto', 'total_optional_components_cost_netto_label', True, 'TableText'),
        ('cost_accessories_aufpreis_netto', 'cost_accessories_aufpreis_netto', True, 'TableText'),
        ('cost_scaffolding_netto', 'cost_scaffolding_netto', True, 'TableText'),
        ('cost_misc_netto', 'cost_misc_netto', True, 'TableText'),
        ('cost_custom_netto', 'cost_custom_netto', True, 'TableText'),
        ('subtotal_netto', 'subtotal_netto', True, 'TableBoldRight'),
        ('one_time_bonus_eur', 'one_time_bonus_eur_label', True, 'TableText'),
        ('total_investment_netto', 'total_investment_netto', True, 'TableBoldRight'),
        ('vat_rate_percent', 'vat_rate_percent', False, 'TableText'),
        ('total_investment_brutto', 'total_investment_brutto', True, 'TableBoldRight'),
    ]
    for result_key, label_key, is_euro_val, base_style_name in cost_items_ordered_pdf:
        value_cost = analysis_results.get(result_key)
        if value_cost is not None:
            if value_cost == 0.0 and result_key not in ['total_investment_netto', 'total_investment_brutto', 'subtotal_netto', 'vat_rate_percent', 'base_matrix_price_netto', 'one_time_bonus_eur']:
                continue
            label_text_pdf = get_text(texts, label_key, label_key.replace("_", " ").title())
            unit_pdf = "€" if is_euro_val else "%" if label_key == 'vat_rate_percent' else ""
            precision_pdf = 1 if label_key == 'vat_rate_percent' else 2
            formatted_value_str_pdf = format_kpi_value(value_cost, unit=unit_pdf, precision=precision_pdf, texts_dict=texts)
            value_style_name = base_style_name
            if result_key in ['total_investment_netto', 'total_investment_brutto', 'subtotal_netto']: value_style_name = 'TableBoldRight'
            elif is_euro_val or unit_pdf == "%": value_style_name = 'TableNumber'
            value_style = STYLES.get(value_style_name, STYLES['TableText'])
            cost_data_pdf.append([Paragraph(str(label_text_pdf), STYLES.get('TableLabel')), Paragraph(str(formatted_value_str_pdf), value_style)])
    return cost_data_pdf

def _prepare_simulation_table_for_pdf(analysis_results: Dict[str, Any], texts: Dict[str, str], num_years_to_show: int = 10) -> List[List[Any]]:
    sim_data_for_pdf_final: List[List[Any]] = []
    header_config_pdf = [
        (get_text(texts,"analysis_table_year_header","Jahr"), None, "", 0, 'TableText'),
        (get_text(texts,"annual_pv_production_kwh","PV Prod."), 'annual_productions_sim', "kWh", 0, 'TableNumber'),
        (get_text(texts,"annual_financial_benefit","Jährl. Vorteil"), 'annual_benefits_sim', "€", 2, 'TableNumber'),
        (get_text(texts,"annual_maintenance_cost_sim","Wartung"), 'annual_maintenance_costs_sim', "€", 2, 'TableNumber'),
        (get_text(texts,"analysis_table_annual_cf_header","Jährl. CF"), 'annual_cash_flows_sim', "€", 2, 'TableNumber'),
        (get_text(texts,"analysis_table_cumulative_cf_header","Kum. CF"), 'cumulative_cash_flows_sim_display', "€", 2, 'TableBoldRight')
    ]
    header_row_pdf = [Paragraph(hc[0], STYLES['TableHeader']) for hc in header_config_pdf]
    sim_data_for_pdf_final.append(header_row_pdf)

    sim_period_eff_pdf = int(analysis_results.get('simulation_period_years_effective', 0))
    if sim_period_eff_pdf == 0: return sim_data_for_pdf_final

    actual_years_to_display_pdf = min(sim_period_eff_pdf, num_years_to_show)
    cumulative_cash_flows_base_sim = analysis_results.get('cumulative_cash_flows_sim', [])
    if cumulative_cash_flows_base_sim and len(cumulative_cash_flows_base_sim) == (sim_period_eff_pdf + 1) :
        analysis_results['cumulative_cash_flows_sim_display'] = cumulative_cash_flows_base_sim[1:]
    else: 
        analysis_results['cumulative_cash_flows_sim_display'] = [None] * sim_period_eff_pdf

    for i_pdf in range(actual_years_to_display_pdf):
        row_items_formatted_pdf = [Paragraph(str(i_pdf + 1), STYLES.get(header_config_pdf[0][4]))]
        for j_pdf, header_conf_item in enumerate(header_config_pdf[1:]):
            result_key_pdf, unit_pdf, precision_pdf, style_name_data_pdf = header_conf_item[1], header_conf_item[2], header_conf_item[3], header_conf_item[4]
            current_list_pdf = analysis_results.get(str(result_key_pdf), [])
            value_to_format_pdf = current_list_pdf[i_pdf] if isinstance(current_list_pdf, list) and i_pdf < len(current_list_pdf) else None
            formatted_str_pdf = format_kpi_value(value_to_format_pdf, unit=unit_pdf, precision=precision_pdf, texts_dict=texts, na_text_key="value_not_available_short_pdf")
            row_items_formatted_pdf.append(Paragraph(str(formatted_str_pdf), STYLES.get(style_name_data_pdf, STYLES['TableText'])))
        sim_data_for_pdf_final.append(row_items_formatted_pdf)

    if sim_period_eff_pdf > num_years_to_show:
        ellipsis_row_pdf = [Paragraph("...", STYLES['TableText']) for _ in header_config_pdf]
        for cell_para_pdf in ellipsis_row_pdf: cell_para_pdf.style.alignment = TA_CENTER
        sim_data_for_pdf_final.append(ellipsis_row_pdf)
    return sim_data_for_pdf_final

def _create_product_table_with_image(details_data_prod: List[List[Any]], product_image_flowables_prod: List[Any], available_width: float) -> List[Any]:
    if not _REPORTLAB_AVAILABLE: return []
    story_elements: List[Any] = []
    if details_data_prod and product_image_flowables_prod:
        text_table_width = available_width * 0.62
        image_cell_width = available_width * 0.35
        text_table = Table(details_data_prod, colWidths=[text_table_width * 0.4, text_table_width * 0.6])
        text_table.setStyle(PRODUCT_TABLE_STYLE)
        image_cell_content = [Spacer(1, 0.1*cm)] + product_image_flowables_prod
        image_frame = KeepInFrame(image_cell_width, 6*cm, image_cell_content)
        combined_table_data = [[text_table, image_frame]]
        combined_table = Table(combined_table_data, colWidths=[text_table_width + 0.03*available_width, image_cell_width])
        combined_table.setStyle(PRODUCT_MAIN_TABLE_STYLE)
        story_elements.append(combined_table)
    elif details_data_prod:
        text_only_table = Table(details_data_prod, colWidths=[available_width * 0.4, available_width * 0.6])
        text_only_table.setStyle(PRODUCT_TABLE_STYLE)
        story_elements.append(text_only_table)
    elif product_image_flowables_prod:
        story_elements.extend(product_image_flowables_prod)
    return story_elements

def _add_product_details_to_story(
    story: List[Any], product_id: Optional[Union[int, float]],
    component_name_text: str, texts: Dict[str,str],
    available_width: float, get_product_by_id_func_param: Callable,
    include_product_images: bool
):
    if not _REPORTLAB_AVAILABLE: return
    product_details: Optional[Dict[str, Any]] = None
    if product_id is not None and callable(get_product_by_id_func_param):
        product_details = get_product_by_id_func_param(product_id)

    if not product_details:
        story.append(Paragraph(f"{component_name_text}: {get_text(texts,'details_not_available_pdf', 'Details nicht verfügbar')}", STYLES.get('NormalLeft')))
        story.append(Spacer(1, 0.3*cm))
        return

    story.append(Paragraph(component_name_text, STYLES.get('ComponentTitle')))
    details_data_prod: List[List[Any]] = [] 

    default_fields_prod = [
        ('brand', 'product_brand'), ('model_name', 'product_model'),
        ('warranty_years', 'product_warranty')
    ]
    component_specific_fields_prod: List[Tuple[str,str]] = []
    cat_lower_prod = str(product_details.get('category', "")).lower()

    if cat_lower_prod == 'modul':
        component_specific_fields_prod = [('capacity_w', 'product_capacity_wp'), ('efficiency_percent', 'product_efficiency'), ('length_m', 'product_length_m'), ('width_m', 'product_width_m'), ('weight_kg', 'product_weight_kg')]
    elif cat_lower_prod == 'wechselrichter':
        component_specific_fields_prod = [('power_kw', 'product_power_kw'), ('efficiency_percent', 'product_efficiency_inverter')]
    elif cat_lower_prod == 'batteriespeicher':
        component_specific_fields_prod = [('storage_power_kw', 'product_capacity_kwh'), ('power_kw', 'product_power_storage_kw'), ('max_cycles', 'product_max_cycles_label')]
    elif cat_lower_prod == 'wallbox':
        component_specific_fields_prod = [('power_kw', 'product_power_wallbox_kw')]
    elif cat_lower_prod == 'energiemanagementsystem': # HINZUGEFÜGT: EMS
        component_specific_fields_prod = [('description', 'product_description_short')] # Beispiel, anpassen!
    elif cat_lower_prod == 'leistungsoptimierer': # HINZUGEFÜGT: Optimierer
        component_specific_fields_prod = [('efficiency_percent', 'product_optimizer_efficiency')] # Beispiel
    elif cat_lower_prod == 'carport': # HINZUGEFÜGT: Carport
        component_specific_fields_prod = [('length_m', 'product_length_m'), ('width_m', 'product_width_m')] # Beispiel
    # Notstrom und Tierabwehr könnten generische Felder wie Beschreibung verwenden oder spezifische, falls vorhanden
    elif cat_lower_prod == 'notstromversorgung':
        component_specific_fields_prod = [('power_kw', 'product_emergency_power_kw')] # Beispiel
    elif cat_lower_prod == 'tierabwehrschutz':
        component_specific_fields_prod = [('description', 'product_description_short')] # Beispiel
    
    all_fields_to_display_prod = default_fields_prod + component_specific_fields_prod
    for key_prod, label_text_key_prod in all_fields_to_display_prod:
        value_prod = product_details.get(key_prod)
        label_prod = get_text(texts, label_text_key_prod, key_prod.replace("_", " ").title())
        
        if value_prod is not None and str(value_prod).strip() != "":
            unit_prod, prec_prod = "", 2
            if key_prod == 'capacity_w': unit_prod, prec_prod = "Wp", 0
            elif key_prod == 'power_kw': unit_prod, prec_prod = "kW", 1 # Für WR, Speicher, Wallbox etc.
            elif key_prod == 'storage_power_kw': unit_prod, prec_prod = "kWh", 1
            elif key_prod.endswith('_percent'): unit_prod, prec_prod = "%", 1
            elif key_prod == 'warranty_years': unit_prod, prec_prod = "Jahre", 0
            elif key_prod == 'max_cycles': unit_prod, prec_prod = "Zyklen", 0
            elif key_prod.endswith('_m'): unit_prod, prec_prod = "m", 3
            elif key_prod == 'weight_kg': unit_prod, prec_prod = "kg", 1
            
            value_str_prod = format_kpi_value(value_prod, unit=unit_prod, precision=prec_prod, texts_dict=texts, na_text_key="value_not_available_short_pdf")
            details_data_prod.append([Paragraph(str(label_prod), STYLES.get('TableLabel')), Paragraph(str(value_str_prod), STYLES.get('TableText'))])

    product_image_flowables_prod: List[Any] = []
    if include_product_images:
        product_image_base64_prod = product_details.get('image_base64')
        if product_image_base64_prod:
            img_w_prod = min(available_width * 0.30, 5*cm); img_h_max_prod = 5*cm
            product_image_flowables_prod = _get_image_flowable(product_image_base64_prod, img_w_prod, texts, None, img_h_max_prod, align='CENTER')
            
    story.extend(_create_product_table_with_image(details_data_prod, product_image_flowables_prod, available_width))
    
    description_prod_val = product_details.get('description')
    if description_prod_val and str(description_prod_val).strip():
        story.append(Spacer(1, 0.2*cm))
        story.append(Paragraph(f"<i>{str(description_prod_val).strip()}</i>", STYLES.get('TableTextSmall')))
    story.append(Spacer(1, 0.5*cm))


def generate_offer_pdf(
    project_data: Dict[str, Any],
    analysis_results: Optional[Dict[str, Any]],
    company_info: Dict[str, Any],
    company_logo_base64: Optional[str],
    selected_title_image_b64: Optional[str],
    selected_offer_title_text: str,
    selected_cover_letter_text: str,
    sections_to_include: Optional[List[str]],
    inclusion_options: Dict[str, Any],
    load_admin_setting_func: Callable, 
    save_admin_setting_func: Callable, 
    list_products_func: Callable, 
    get_product_by_id_func: Callable, 
    db_list_company_documents_func: Callable[[int, Optional[str]], List[Dict[str, Any]]],
    active_company_id: Optional[int],
    texts: Dict[str, str]
) -> Optional[bytes]:

    if not _REPORTLAB_AVAILABLE:
        if project_data and texts and company_info:
            return _create_plaintext_pdf_fallback(project_data, analysis_results, texts, company_info, selected_offer_title_text, selected_cover_letter_text)
        return None

    design_settings = load_admin_setting_func('pdf_design_settings', {'primary_color': PRIMARY_COLOR_HEX, 'secondary_color': SECONDARY_COLOR_HEX})
    if isinstance(design_settings, dict):
        _update_styles_with_dynamic_colors(design_settings)

    main_offer_buffer = io.BytesIO()
    offer_number_final = _get_next_offer_number(texts, load_admin_setting_func, save_admin_setting_func)

    include_company_logo_opt = inclusion_options.get("include_company_logo", True)
    include_product_images_opt = inclusion_options.get("include_product_images", True)
    include_all_documents_opt = inclusion_options.get("include_all_documents", False) # Korrigierter Key
    company_document_ids_to_include_opt = inclusion_options.get("company_document_ids_to_include", [])
    include_optional_component_details_opt = inclusion_options.get("include_optional_component_details", True) # NEUE Option

    doc = SimpleDocTemplate(main_offer_buffer, title=get_text(texts, "pdf_offer_title_doc_param", "Angebot: Photovoltaikanlage").format(offer_number=offer_number_final),
                            author=company_info.get("name", "SolarFirma"), pagesize=pagesizes.A4,
                            leftMargin=2*cm, rightMargin=2*cm, topMargin=2.5*cm, bottomMargin=2.5*cm)

    story: List[Any] = []
    
    current_project_data_pdf = project_data if isinstance(project_data, dict) else {}
    current_analysis_results_pdf = analysis_results if isinstance(analysis_results, dict) else {}
    customer_pdf = current_project_data_pdf.get("customer_data", {})
    pv_details_pdf = current_project_data_pdf.get("project_details", {})
    available_width_content = doc.width

    # --- Deckblatt ---
    try:
        if selected_title_image_b64:
            img_flowables_title = _get_image_flowable(selected_title_image_b64, doc.width, texts, max_height=doc.height / 1.8, align='CENTER')
            if img_flowables_title: story.extend(img_flowables_title); story.append(Spacer(1, 0.5 * cm))

        if include_company_logo_opt and company_logo_base64:
            logo_flowables_deckblatt = _get_image_flowable(company_logo_base64, 6*cm, texts, max_height=3*cm, align='CENTER')
            if logo_flowables_deckblatt: story.extend(logo_flowables_deckblatt); story.append(Spacer(1, 0.5 * cm))

        offer_title_processed_pdf = _replace_placeholders(selected_offer_title_text, customer_pdf, company_info, offer_number_final, texts, current_analysis_results_pdf)
        story.append(Paragraph(offer_title_processed_pdf, STYLES.get('OfferTitle')))
        
        company_info_html_pdf = "<br/>".join(filter(None, [
            f"<b>{company_info.get('name', '')}</b>", company_info.get("street", ""),
            f"{company_info.get('zip_code', '')} {company_info.get('city', '')}".strip(),
            (f"{get_text(texts, 'pdf_phone_label_short', 'Tel.')}: {company_info.get('phone', '')}" if company_info.get('phone') else None),
            (f"{get_text(texts, 'pdf_email_label_short', 'Mail')}: {company_info.get('email', '')}" if company_info.get('email') else None),
            (f"{get_text(texts, 'pdf_website_label_short', 'Web')}: {company_info.get('website', '')}" if company_info.get('website') else None),
            (f"{get_text(texts, 'pdf_taxid_label', 'StNr/USt-ID')}: {company_info.get('tax_id', '')}" if company_info.get('tax_id') else None),
        ]))
        story.append(Paragraph(company_info_html_pdf, STYLES.get('CompanyInfoDeckblatt')))
        
        customer_name_display_pdf = f"{customer_pdf.get('salutation','')} {customer_pdf.get('title','')} {customer_pdf.get('first_name','')} {customer_pdf.get('last_name','')}".replace(" None ", " ").replace("  ", " ").strip()
        if not customer_name_display_pdf: customer_name_display_pdf = customer_pdf.get("company_name", get_text(texts, "customer_name_fallback_pdf", "Interessent"))

        customer_address_block_pdf_lines = [customer_name_display_pdf]
        if customer_pdf.get("company_name") and customer_name_display_pdf != customer_pdf.get("company_name"):
            customer_address_block_pdf_lines.append(str(customer_pdf.get("company_name")))
        customer_address_block_pdf_lines.extend([
            f"{str(customer_pdf.get('address',''))} {str(customer_pdf.get('house_number','',))}".strip(),
            f"{str(customer_pdf.get('zip_code',''))} {str(customer_pdf.get('city','',))}".strip()
        ])
        customer_address_block_pdf = "<br/>".join(filter(None, customer_address_block_pdf_lines))
        story.append(Paragraph(customer_address_block_pdf, STYLES.get("CustomerAddress")))
        
        story.append(Spacer(1, 0.2 * cm))
        story.append(Paragraph(f"{get_text(texts, 'pdf_offer_number_label', 'Angebotsnummer')}: <b>{offer_number_final}</b>", STYLES.get('NormalRight')))
        story.append(Paragraph(f"{get_text(texts, 'pdf_offer_date_label', 'Datum')}: {datetime.now().strftime('%d.%m.%Y')}", STYLES.get('NormalRight')))
        story.append(PageBreak())
    except Exception as e_cover:
        story.append(Paragraph(f"Fehler bei Erstellung des Deckblatts: {e_cover}", STYLES.get('NormalLeft')))
        story.append(PageBreak())

    # --- Anschreiben ---
    try:
        story.append(SetCurrentChapterTitle(get_text(texts, "pdf_chapter_title_cover_letter", "Anschreiben")))
        company_sender_address_lines = [company_info.get("name", ""), company_info.get("street", ""), f"{company_info.get('zip_code','')} {company_info.get('city','')}".strip()]
        story.append(Paragraph("<br/>".join(filter(None,company_sender_address_lines)), STYLES.get('NormalLeft'))) 
        story.append(Spacer(1, 1.5*cm))
        story.append(Paragraph(customer_address_block_pdf, STYLES.get('NormalLeft')))
        story.append(Spacer(1, 1*cm))
        story.append(Paragraph(datetime.now().strftime('%d.%m.%Y'), STYLES.get('NormalRight')))
        story.append(Spacer(1, 0.5*cm))
        offer_subject_text = get_text(texts, "pdf_offer_subject_line_param", "Ihr persönliches Angebot für eine Photovoltaikanlage, Nr. {offer_number}").format(offer_number=offer_number_final)
        story.append(Paragraph(f"<b>{offer_subject_text}</b>", STYLES.get('NormalLeft')))
        story.append(Spacer(1, 0.5*cm))

        cover_letter_processed_pdf = _replace_placeholders(selected_cover_letter_text, customer_pdf, company_info, offer_number_final, texts, current_analysis_results_pdf)
        cover_letter_paragraphs = cover_letter_processed_pdf.split('\n') 
        for para_text in cover_letter_paragraphs:
            if para_text.strip(): 
                story.append(Paragraph(para_text.replace('\r',''), STYLES.get('CoverLetter'))) 
            else: 
                story.append(Spacer(1, 0.2*cm)) 
        story.append(Spacer(1, 1*cm))
        story.append(Paragraph(get_text(texts, "pdf_closing_greeting", "Mit freundlichen Grüßen"), STYLES.get('NormalLeft')))
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph(str(company_info.get("name", "")), STYLES.get('NormalLeft')))
        story.append(PageBreak())
    except Exception as e_letter:
        story.append(Paragraph(f"Fehler bei Erstellung des Anschreibens: {e_letter}", STYLES.get('NormalLeft')))
        story.append(PageBreak())

    # --- Dynamische Sektionen ---
    active_sections_set_pdf = set(sections_to_include or [])
    section_chapter_titles_map = { 
        "ProjectOverview": get_text(texts, "pdf_chapter_title_overview", "Projektübersicht"),
        "TechnicalComponents": get_text(texts, "pdf_chapter_title_components", "Komponenten"),
        "CostDetails": get_text(texts, "pdf_chapter_title_cost_details", "Kosten"),
        "Economics": get_text(texts, "pdf_chapter_title_economics", "Wirtschaftlichkeit"),
        "SimulationDetails": get_text(texts, "pdf_chapter_title_simulation", "Simulation"),
        "CO2Savings": get_text(texts, "pdf_chapter_title_co2", "CO₂-Einsparung"),
        "Visualizations": get_text(texts, "pdf_chapter_title_visualizations", "Visualisierungen"),
        "FutureAspects": get_text(texts, "pdf_chapter_title_future_aspects", "Zukunftsaspekte")
    }
    ordered_section_definitions_pdf = [ 
        ("ProjectOverview", "pdf_section_title_overview", "1. Projektübersicht & Eckdaten"),
        ("TechnicalComponents", "pdf_section_title_components", "2. Angebotene Systemkomponenten"),
        ("CostDetails", "pdf_section_title_cost_details", "3. Detaillierte Kostenaufstellung"),
        ("Economics", "pdf_section_title_economics", "4. Wirtschaftlichkeit im Überblick"),
        ("SimulationDetails", "pdf_section_title_simulation", "5. Simulationsübersicht (Auszug)"),
        ("CO2Savings", "pdf_section_title_co2", "6. Ihre CO₂-Einsparung"),
        ("Visualizations", "pdf_section_title_visualizations", "7. Grafische Auswertungen"),
        ("FutureAspects", "pdf_chapter_title_future_aspects", "8. Zukunftsaspekte & Erweiterungen"),
    ]

    current_section_counter_pdf = 1
    for section_key_current, title_text_key_current, default_title_current in ordered_section_definitions_pdf:
        if section_key_current in active_sections_set_pdf:
            try:
                chapter_title_for_header_current = section_chapter_titles_map.get(section_key_current, default_title_current.split('. ',1)[-1] if '. ' in default_title_current else default_title_current)
                story.append(SetCurrentChapterTitle(chapter_title_for_header_current))
                numbered_title_current = f"{current_section_counter_pdf}. {get_text(texts, title_text_key_current, default_title_current.split('. ',1)[-1] if '. ' in default_title_current else default_title_current)}"
                story.append(Paragraph(numbered_title_current, STYLES.get('SectionTitle')))
                story.append(Spacer(1, 0.2 * cm))

                if section_key_current == "ProjectOverview":
                    if pv_details_pdf.get('visualize_roof_in_pdf_satellite', False) and pv_details_pdf.get('satellite_image_base64_data'):
                        story.append(Paragraph(get_text(texts,"satellite_image_header_pdf","Satellitenansicht Objekt"), STYLES.get('SubSectionTitle')))
                        sat_img_flowables = _get_image_flowable(pv_details_pdf['satellite_image_base64_data'], available_width_content * 0.8, texts, caption_text_key="satellite_image_caption_pdf", max_height=10*cm)
                        if sat_img_flowables: story.extend(sat_img_flowables); story.append(Spacer(1, 0.5*cm))
                    
                    overview_data_content_pdf = [
                        [get_text(texts,"anlage_size_label_pdf", "Anlagengröße"),format_kpi_value(current_analysis_results_pdf.get('anlage_kwp'),"kWp",texts_dict=texts, na_text_key="value_not_available_short_pdf")],
                        [get_text(texts,"module_quantity_label_pdf","Anzahl Module"),str(pv_details_pdf.get('module_quantity', get_text(texts, "value_not_available_short_pdf")))],
                        [get_text(texts,"annual_pv_production_kwh_pdf", "Jährliche PV-Produktion (ca.)"),format_kpi_value(current_analysis_results_pdf.get('annual_pv_production_kwh'),"kWh",precision=0,texts_dict=texts, na_text_key="value_not_available_short_pdf")],
                        [get_text(texts,"self_supply_rate_percent_pdf", "Autarkiegrad (ca.)"),format_kpi_value(current_analysis_results_pdf.get('self_supply_rate_percent'),"%",precision=1,texts_dict=texts, na_text_key="value_not_available_short_pdf")],
                    ]
                    if pv_details_pdf.get('include_storage'):
                         overview_data_content_pdf.extend([[get_text(texts,"selected_storage_capacity_label_pdf", "Speicherkapazität"),format_kpi_value(pv_details_pdf.get('selected_storage_storage_power_kw'),"kWh",texts_dict=texts, na_text_key="value_not_available_short_pdf")]])
                    if overview_data_content_pdf:
                        overview_table_data_styled_content_pdf = [[Paragraph(str(cell[0]),STYLES.get('TableLabel')),Paragraph(str(cell[1]),STYLES.get('TableText'))] for cell in overview_data_content_pdf]
                        overview_table_content_pdf = Table(overview_table_data_styled_content_pdf,colWidths=[available_width_content*0.5,available_width_content*0.5])
                        overview_table_content_pdf.setStyle(TABLE_STYLE_DEFAULT); story.append(overview_table_content_pdf)

                elif section_key_current == "TechnicalComponents":
                    story.append(Paragraph(get_text(texts, "pdf_components_intro", "Nachfolgend die Details zu den Kernkomponenten Ihrer Anlage:"), STYLES.get('NormalLeft')))
                    story.append(Spacer(1, 0.3*cm))
                    
                    main_components = [
                        (pv_details_pdf.get("selected_module_id"), get_text(texts, "pdf_component_module_title", "PV-Module")),
                        (pv_details_pdf.get("selected_inverter_id"), get_text(texts, "pdf_component_inverter_title", "Wechselrichter")),
                    ]
                    if pv_details_pdf.get("include_storage"):
                        main_components.append((pv_details_pdf.get("selected_storage_id"), get_text(texts, "pdf_component_storage_title", "Batteriespeicher")))
                    
                    for comp_id, comp_title in main_components:
                        if comp_id: _add_product_details_to_story(story, comp_id, comp_title, texts, available_width_content, get_product_by_id_func, include_product_images_opt)

                    # ERWEITERUNG: Optionale Komponenten / Zubehör
                    if pv_details_pdf.get('include_additional_components', False) and include_optional_component_details_opt:
                        story.append(Paragraph(get_text(texts, "pdf_additional_components_header_pdf", "Optionale Komponenten"), STYLES.get('SubSectionTitle')))
                        optional_comps_map = {
                            'selected_wallbox_id': get_text(texts, "pdf_component_wallbox_title", "Wallbox"),
                            'selected_ems_id': get_text(texts, "pdf_component_ems_title", "Energiemanagementsystem"),
                            'selected_optimizer_id': get_text(texts, "pdf_component_optimizer_title", "Leistungsoptimierer"),
                            'selected_carport_id': get_text(texts, "pdf_component_carport_title", "Solarcarport"),
                            'selected_notstrom_id': get_text(texts, "pdf_component_emergency_power_title", "Notstromversorgung"),
                            'selected_tierabwehr_id': get_text(texts, "pdf_component_animal_defense_title", "Tierabwehrschutz")
                        }
                        any_optional_component_rendered = False
                        for key, title in optional_comps_map.items():
                            opt_comp_id = pv_details_pdf.get(key)
                            if opt_comp_id: 
                                _add_product_details_to_story(story, opt_comp_id, title, texts, available_width_content, get_product_by_id_func, include_product_images_opt)
                                any_optional_component_rendered = True
                        if not any_optional_component_rendered:
                            story.append(Paragraph(get_text(texts, "pdf_no_optional_components_selected_for_details", "Keine optionalen Komponenten für Detailanzeige ausgewählt."), STYLES.get('NormalLeft')))


                elif section_key_current == "CostDetails":
                    cost_table_data_final_pdf = _prepare_cost_table_for_pdf(current_analysis_results_pdf, texts)
                    if cost_table_data_final_pdf:
                        cost_table_obj_final_pdf = Table(cost_table_data_final_pdf, colWidths=[available_width_content*0.6, available_width_content*0.4])
                        cost_table_obj_final_pdf.setStyle(TABLE_STYLE_DEFAULT); story.append(cost_table_obj_final_pdf)
                        if current_analysis_results_pdf.get('base_matrix_price_netto', 0.0) == 0 and current_analysis_results_pdf.get('cost_storage_aufpreis_product_db_netto', 0.0) > 0: story.append(Spacer(1,0.2*cm)); story.append(Paragraph(get_text(texts, "analysis_storage_cost_note_single_price_pdf", "<i>Hinweis: Speicherkosten als Einzelposten, da kein Matrix-Pauschalpreis.</i>"), STYLES.get('TableTextSmall')))
                        elif current_analysis_results_pdf.get('base_matrix_price_netto', 0.0) > 0 and current_analysis_results_pdf.get('cost_storage_aufpreis_product_db_netto', 0.0) > 0 : story.append(Spacer(1,0.2*cm)); story.append(Paragraph(get_text(texts, "analysis_storage_cost_note_matrix_pdf", "<i>Hinweis: Speicherkosten als Aufpreis, da Matrixpreis 'Ohne Speicher' verwendet wurde.</i>"), STYLES.get('TableTextSmall')))

                elif section_key_current == "Economics":
                    eco_kpi_data_for_pdf_table = [
                        [get_text(texts, "total_investment_brutto_pdf", "Gesamtinvestition (Brutto)"), format_kpi_value(current_analysis_results_pdf.get('total_investment_brutto'), "€", texts_dict=texts, na_text_key="value_not_calculated_short_pdf")],
                        [get_text(texts, "annual_financial_benefit_pdf", "Finanzieller Vorteil (Jahr 1, ca.)"), format_kpi_value(current_analysis_results_pdf.get('annual_financial_benefit_year1'), "€", texts_dict=texts, na_text_key="value_not_calculated_short_pdf")],
                        [get_text(texts, "amortization_time_years_pdf", "Amortisationszeit (ca.)"), format_kpi_value(current_analysis_results_pdf.get('amortization_time_years'), "Jahre", texts_dict=texts, na_text_key="value_not_calculated_short_pdf")],
                        [get_text(texts, "simple_roi_percent_label_pdf", "Einfache Rendite (Jahr 1, ca.)"), format_kpi_value(current_analysis_results_pdf.get('simple_roi_percent'), "%", precision=1, texts_dict=texts, na_text_key="value_not_calculated_short_pdf")],
                        [get_text(texts, "lcoe_euro_per_kwh_label_pdf", "Stromgestehungskosten (LCOE, ca.)"), format_kpi_value(current_analysis_results_pdf.get('lcoe_euro_per_kwh'), "€/kWh", precision=3, texts_dict=texts, na_text_key="value_not_calculated_short_pdf")],
                        [get_text(texts, "npv_over_years_pdf", "Kapitalwert über Laufzeit (NPV, ca.)"), format_kpi_value(current_analysis_results_pdf.get('npv_value'), "€", texts_dict=texts, na_text_key="value_not_calculated_short_pdf")],
                        [get_text(texts, "irr_percent_pdf", "Interner Zinsfuß (IRR, ca.)"), format_kpi_value(current_analysis_results_pdf.get('irr_percent'), "%", precision=1, texts_dict=texts, na_text_key="value_not_calculated_short_pdf")]
                    ]
                    if eco_kpi_data_for_pdf_table:
                        eco_kpi_table_styled_content = [[Paragraph(str(cell[0]), STYLES.get('TableLabel')), Paragraph(str(cell[1]), STYLES.get('TableNumber'))] for cell in eco_kpi_data_for_pdf_table]
                        eco_table_object = Table(eco_kpi_table_styled_content, colWidths=[available_width_content*0.6, available_width_content*0.4])
                        eco_table_object.setStyle(TABLE_STYLE_DEFAULT); story.append(eco_table_object)

                elif section_key_current == "SimulationDetails":
                    sim_table_data_content_pdf = _prepare_simulation_table_for_pdf(current_analysis_results_pdf, texts, num_years_to_show=10)
                    if len(sim_table_data_content_pdf) > 1:
                        sim_table_obj_final_pdf = Table(sim_table_data_content_pdf, colWidths=None)
                        sim_table_obj_final_pdf.setStyle(DATA_TABLE_STYLE); story.append(sim_table_obj_final_pdf)
                    else: story.append(Paragraph(get_text(texts, "pdf_simulation_data_not_available", "Simulationsdetails nicht ausreichend für Tabellendarstellung."), STYLES.get('NormalLeft')))

                elif section_key_current == "CO2Savings":
                    co2_savings_val = current_analysis_results_pdf.get('annual_co2_savings_kg', 0.0)
                    co2_text = get_text(texts, "pdf_annual_co2_savings_param_pdf", "Durch Ihre neue Photovoltaikanlage vermeiden Sie jährlich ca. <b>{co2_savings_kg_formatted} kg CO₂</b>. Dies entspricht der Bindungskapazität von etwa <b>{trees_equiv:.0f} Bäumen</b> oder der Vermeidung von ca. <b>{car_km_equiv:.0f} Autokilometern</b>.").format(
                        co2_savings_kg_formatted=format_kpi_value(co2_savings_val, "", precision=0, texts_dict=texts),
                        trees_equiv=current_analysis_results_pdf.get('co2_equivalent_trees_per_year', 0.0),
                        car_km_equiv=current_analysis_results_pdf.get('co2_equivalent_car_km_per_year', 0.0)
                    )
                    story.append(Paragraph(co2_text, STYLES.get('NormalLeft')))

                elif section_key_current == "Visualizations":
                    story.append(Paragraph(get_text(texts, "pdf_visualizations_intro", "Die folgenden Diagramme visualisieren die Ergebnisse Ihrer Photovoltaikanlage und deren Wirtschaftlichkeit:"), STYLES.get('NormalLeft')))
                    story.append(Spacer(1, 0.3 * cm))
                    
                    # ERWEITERUNG: Vollständige Liste der Diagramme für PDF-Auswahl
                    # Diese Map sollte idealerweise mit `chart_key_to_friendly_name_map` aus `pdf_ui.py` synchronisiert werden.
                    charts_config_for_pdf_generator = {
                        'monthly_prod_cons_chart_bytes': {"title_key": "pdf_chart_title_monthly_comp_pdf", "default_title": "Monatl. Produktion/Verbrauch (2D)"},
                        'cost_projection_chart_bytes': {"title_key": "pdf_chart_label_cost_projection", "default_title": "Stromkosten-Hochrechnung (2D)"},
                        'cumulative_cashflow_chart_bytes': {"title_key": "pdf_chart_label_cum_cashflow", "default_title": "Kumulierter Cashflow (2D)"},
                        'consumption_coverage_pie_chart_bytes': {"title_key": "pdf_chart_title_consumption_coverage_pdf", "default_title": "Deckung Gesamtverbrauch (Jahr 1)"},
                        'pv_usage_pie_chart_bytes': {"title_key": "pdf_chart_title_pv_usage_pdf", "default_title": "Nutzung PV-Strom (Jahr 1)"},
                        'daily_production_switcher_chart_bytes': {"title_key": "pdf_chart_label_daily_3d", "default_title": "Tagesproduktion (3D)"},
                        'weekly_production_switcher_chart_bytes': {"title_key": "pdf_chart_label_weekly_3d", "default_title": "Wochenproduktion (3D)"},
                        'yearly_production_switcher_chart_bytes': {"title_key": "pdf_chart_label_yearly_3d_bar", "default_title": "Jahresproduktion (3D-Balken)"},
                        'project_roi_matrix_switcher_chart_bytes': {"title_key": "pdf_chart_label_roi_matrix_3d", "default_title": "Projektrendite-Matrix (3D)"},
                        'feed_in_revenue_switcher_chart_bytes': {"title_key": "pdf_chart_label_feedin_3d", "default_title": "Einspeisevergütung (3D)"},
                        'prod_vs_cons_switcher_chart_bytes': {"title_key": "pdf_chart_label_prodcons_3d", "default_title": "Verbr. vs. Prod. (3D)"},
                        'tariff_cube_switcher_chart_bytes': {"title_key": "pdf_chart_label_tariffcube_3d", "default_title": "Tarifvergleich (3D)"},
                        'co2_savings_value_switcher_chart_bytes': {"title_key": "pdf_chart_label_co2value_3d", "default_title": "CO2-Ersparnis vs. Wert (3D)"},
                        'investment_value_switcher_chart_bytes': {"title_key": "pdf_chart_label_investval_3D", "default_title": "Investitionsnutzwert (3D)"},
                        'storage_effect_switcher_chart_bytes': {"title_key": "pdf_chart_label_storageeff_3d", "default_title": "Speicherwirkung (3D)"},
                        'selfuse_stack_switcher_chart_bytes': {"title_key": "pdf_chart_label_selfusestack_3d", "default_title": "Eigenverbr. vs. Einspeis. (3D)"},
                        'cost_growth_switcher_chart_bytes': {"title_key": "pdf_chart_label_costgrowth_3d", "default_title": "Stromkostensteigerung (3D)"},
                        'selfuse_ratio_switcher_chart_bytes': {"title_key": "pdf_chart_label_selfuseratio_3d", "default_title": "Eigenverbrauchsgrad (3D)"},
                        'roi_comparison_switcher_chart_bytes': {"title_key": "pdf_chart_label_roicompare_3d", "default_title": "ROI-Vergleich (3D)"},
                        'scenario_comparison_switcher_chart_bytes': {"title_key": "pdf_chart_label_scenariocomp_3d", "default_title": "Szenarienvergleich (3D)"},
                        'tariff_comparison_switcher_chart_bytes': {"title_key": "pdf_chart_label_tariffcomp_3d", "default_title": "Vorher/Nachher Stromkosten (3D)"},
                        'income_projection_switcher_chart_bytes': {"title_key": "pdf_chart_label_incomeproj_3d", "default_title": "Einnahmenprognose (3D)"},
                        'yearly_production_chart_bytes': {"title_key": "pdf_chart_label_pvvis_yearly", "default_title": "PV Visuals: Jahresproduktion"},
                        'break_even_chart_bytes': {"title_key": "pdf_chart_label_pvvis_breakeven", "default_title": "PV Visuals: Break-Even"},
                        'amortisation_chart_bytes': {"title_key": "pdf_chart_label_pvvis_amort", "default_title": "PV Visuals: Amortisation"},
                    }
                    charts_added_count = 0
                    selected_charts_for_pdf_opt = inclusion_options.get("selected_charts_for_pdf", [])
                    
                    for chart_key, config in charts_config_for_pdf_generator.items():
                        if chart_key not in selected_charts_for_pdf_opt:
                            continue # Überspringe dieses Diagramm, wenn nicht vom Nutzer ausgewählt

                        chart_image_bytes = current_analysis_results_pdf.get(chart_key)
                        if chart_image_bytes and isinstance(chart_image_bytes, bytes):
                            chart_display_title = get_text(texts, config["title_key"], config["default_title"])
                            story.append(Paragraph(chart_display_title, STYLES.get('ChartTitle')))
                            img_flowables_chart = _get_image_flowable(chart_image_bytes, available_width_content * 0.9, texts, max_height=12*cm, align='CENTER')
                            if img_flowables_chart: story.extend(img_flowables_chart); story.append(Spacer(1, 0.7*cm)); charts_added_count += 1
                            else: story.append(Paragraph(get_text(texts, "pdf_chart_load_error_placeholder_param", f"(Fehler beim Laden: {chart_display_title})"), STYLES.get('NormalCenter'))); story.append(Spacer(1, 0.5*cm))
                    if charts_added_count == 0 and selected_charts_for_pdf_opt : # Wenn Charts ausgewählt wurden, aber keine gerendert werden konnten
                         story.append(Paragraph(get_text(texts, "pdf_selected_charts_not_renderable", "Ausgewählte Diagramme konnten nicht geladen/angezeigt werden."), STYLES.get('NormalCenter')))
                    elif not selected_charts_for_pdf_opt : # Wenn gar keine Charts ausgewählt wurden
                         story.append(Paragraph(get_text(texts, "pdf_no_charts_selected_for_section", "Keine Diagramme für diese Sektion ausgewählt."), STYLES.get('NormalCenter')))


                elif section_key_current == "FutureAspects":
                    future_aspects_text = ""
                    if pv_details_pdf.get('future_ev'):
                        future_aspects_text += get_text(texts, "pdf_future_ev_text_param", "<b>E-Mobilität:</b> Die Anlage ist auf eine zukünftige Erweiterung um ein Elektrofahrzeug vorbereitet. Der prognostizierte PV-Anteil an der Fahrzeugladung beträgt ca. {eauto_pv_coverage_kwh:.0f} kWh/Jahr.").format(eauto_pv_coverage_kwh=current_analysis_results_pdf.get('eauto_ladung_durch_pv_kwh',0.0)) + "<br/>"
                    if pv_details_pdf.get('future_hp'):
                        future_aspects_text += get_text(texts, "pdf_future_hp_text_param", "<b>Wärmepumpe:</b> Die Anlage kann zur Unterstützung einer zukünftigen Wärmepumpe beitragen. Der geschätzte PV-Deckungsgrad für die Wärmepumpe liegt bei ca. {hp_pv_coverage_pct:.0f}%. ").format(hp_pv_coverage_pct=current_analysis_results_pdf.get('pv_deckungsgrad_wp_pct',0.0)) + "<br/>"
                    if not future_aspects_text: future_aspects_text = get_text(texts, "pdf_no_future_aspects_selected", "Keine spezifischen Zukunftsaspekte für dieses Angebot ausgewählt.")
                    story.append(Paragraph(future_aspects_text, STYLES.get('NormalLeft')))

                story.append(Spacer(1, 0.5*cm)); current_section_counter_pdf +=1
            except Exception as e_section:
                story.append(Paragraph(f"Fehler in Sektion '{default_title_current}': {e_section}", STYLES.get('NormalLeft')))
                story.append(Spacer(1, 0.5*cm)); current_section_counter_pdf +=1
    
    main_pdf_bytes: Optional[bytes] = None
    try:
        layout_callback_kwargs_build = {
            'texts_ref': texts, 'company_info_ref': company_info,
            'company_logo_base64_ref': company_logo_base64 if include_company_logo_opt else None,
            'offer_number_ref': offer_number_final, 'page_width_ref': doc.pagesize[0], 
            'page_height_ref': doc.pagesize[1],'margin_left_ref': doc.leftMargin, 
            'margin_right_ref': doc.rightMargin,'margin_top_ref': doc.topMargin, 
            'margin_bottom_ref': doc.bottomMargin,'doc_width_ref': doc.width, 'doc_height_ref': doc.height
        }
        doc.build(story, canvasmaker=lambda *args, **kwargs_c: PageNumCanvas(*args, onPage_callback=page_layout_handler, callback_kwargs=layout_callback_kwargs_build, **kwargs_c))
        main_pdf_bytes = main_offer_buffer.getvalue()
    except Exception as e_build_pdf:
        return _create_plaintext_pdf_fallback(project_data, analysis_results, texts, company_info, selected_offer_title_text, selected_cover_letter_text)
    finally:
        main_offer_buffer.close()

    if not main_pdf_bytes: return None

    if not (include_all_documents_opt and _PYPDF_AVAILABLE):
        return main_pdf_bytes

    paths_to_append: List[str] = []
    # Produktdatenblätter (Hauptkomponenten UND Zubehör)
    product_ids_for_datasheets = list(filter(None, [
        pv_details_pdf.get("selected_module_id"),
        pv_details_pdf.get("selected_inverter_id"),
        pv_details_pdf.get("selected_storage_id") if pv_details_pdf.get("include_storage") else None
    ]))
    if pv_details_pdf.get('include_additional_components', False): # Nur wenn Zubehör überhaupt aktiv ist
        for opt_id_key in ['selected_wallbox_id', 'selected_ems_id', 'selected_optimizer_id', 'selected_carport_id', 'selected_notstrom_id', 'selected_tierabwehr_id']:
            comp_id_val = pv_details_pdf.get(opt_id_key)
            if comp_id_val: product_ids_for_datasheets.append(comp_id_val)
    
    # Duplikate entfernen, falls ein Produkt mehrfach auftaucht (unwahrscheinlich, aber sicher)
    product_ids_for_datasheets = list(set(product_ids_for_datasheets))


    for prod_id in product_ids_for_datasheets:
        product_info = get_product_by_id_func(prod_id) 
        if product_info and product_info.get("datasheet_link_db_path"):
            relative_datasheet_path = product_info["datasheet_link_db_path"]
            full_datasheet_path = os.path.join(PRODUCT_DATASHEETS_BASE_DIR_PDF_GEN, relative_datasheet_path)
            if os.path.exists(full_datasheet_path): paths_to_append.append(full_datasheet_path)
            
    # Firmendokumente
    if company_document_ids_to_include_opt and active_company_id is not None and callable(db_list_company_documents_func):
        all_company_docs_for_active_co = db_list_company_documents_func(active_company_id, None) # doc_type=None für alle
        for doc_info in all_company_docs_for_active_co:
            if doc_info.get('id') in company_document_ids_to_include_opt:
                relative_doc_path = doc_info.get("relative_db_path") 
                if relative_doc_path: 
                    full_doc_path = os.path.join(COMPANY_DOCS_BASE_DIR_PDF_GEN, relative_doc_path)
                    if os.path.exists(full_doc_path): paths_to_append.append(full_doc_path)
                    
    if not paths_to_append: return main_pdf_bytes

    pdf_writer = PdfWriter()
    try:
        main_offer_reader = PdfReader(io.BytesIO(main_pdf_bytes))
        for page in main_offer_reader.pages: pdf_writer.add_page(page)
    except Exception as e_read_main:
        return main_pdf_bytes 

    for pdf_path in paths_to_append:
        try:
            datasheet_reader = PdfReader(pdf_path)
            for page in datasheet_reader.pages: pdf_writer.add_page(page)
        except Exception as e_append_ds:
            pass 

    final_buffer = io.BytesIO()
    try:
        pdf_writer.write(final_buffer)
        final_pdf_bytes = final_buffer.getvalue()
        return final_pdf_bytes
    except Exception as e_write_final:
        return main_pdf_bytes 
    finally:
        final_buffer.close()

def _create_plaintext_pdf_fallback(project_data: Dict[str, Any], analysis_results: Optional[Dict[str, Any]], texts: Dict[str, str], company_info: Dict[str, Any], pdf_offer_title_template: str, pdf_cover_letter_text: str) -> bytes:
    buffer_fallback = io.StringIO()
    buffer_fallback.write(f"{get_text(texts, 'pdf_plaintext_title_pdf', 'PV-Angebot (Textversion)')}\n{'='*40}\n\n")
    customer_fb = project_data.get("customer_data", {})
    calc_res_fb = analysis_results if isinstance(analysis_results, dict) else {}
    buffer_fallback.write(f"{get_text(texts, 'pdf_offer_title_label_fb', 'Angebotstitel')}: {pdf_offer_title_template}\n")
    buffer_fallback.write(f"{get_text(texts, 'pdf_date_label_fb', 'Datum')}: {datetime.now().strftime('%d.%m.%Y')}\n\n")
    buffer_fallback.write(f"{get_text(texts, 'pdf_company_label_fb', 'Firma')}: {company_info.get('name', 'N/A')}\n")
    anschreiben_fb = _replace_placeholders(pdf_cover_letter_text, customer_fb, company_info, "FALLBACK_NR", texts, calc_res_fb)
    buffer_fallback.write(f"\n{get_text(texts, 'pdf_cover_letter_label_fb', 'Anschreiben')}:\n{anschreiben_fb}\n\n")
    buffer_fallback.write(f"\n--- {get_text(texts, 'pdf_section_title_overview_fb', 'Projektübersicht')} ---\n")
    anlage_kwp_fb_val = calc_res_fb.get('anlage_kwp')
    buffer_fallback.write(f"{get_text(texts, 'anlage_size_label_pdf_fb', 'Anlagengröße')}: {format_kpi_value(anlage_kwp_fb_val, 'kWp', texts_dict=texts, na_text_key='value_not_available_short_pdf')}\n")
    buffer_fallback.write(f"\n({get_text(texts, 'pdf_plaintext_fallback_note', 'Dies ist eine vereinfachte Textversion des Angebots aufgrund eines Fehlers bei der PDF-Erstellung.')})\n")
    return buffer_fallback.getvalue().encode('utf-8')

# Änderungshistorie
# 2025-06-03, Gemini Ultra: PageNumCanvas.save() korrigiert, um Duplizierung des PDF-Inhalts zu verhindern.
#                           Schlüssel für `include_all_documents_opt` in `generate_offer_pdf` korrigiert.
#                           Aufruf von `db_list_company_documents_func` mit `doc_type=None` versehen.
#                           Anpassung von _update_styles_with_dynamic_colors für DATA_TABLE_STYLE.
#                           Sicherstellung, dass ausgewählte Diagramme für PDF-Visualisierungen berücksichtigt werden.
#                           Korrekter Key 'relative_db_path' für Firmendokumente verwendet.
# 2025-06-03, Gemini Ultra: `charts_config_for_pdf_generator` erweitert, um alle Diagramme aus `pdf_ui.py` abzudecken.
#                           Logik zur Einbindung optionaler Komponenten (Zubehör) in Sektion "Technische Komponenten" hinzugefügt, gesteuert durch `include_optional_component_details_opt`.
#                           Logik zum Anhängen von Produktdatenblättern erweitert, um auch Zubehör-Datenblätter zu berücksichtigen.
#                           Definition von ReportLab-Styles nur ausgeführt, wenn _REPORTLAB_AVAILABLE True ist.