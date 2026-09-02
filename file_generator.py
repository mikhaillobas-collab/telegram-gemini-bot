import io
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

logger = logging.getLogger(__name__)

# --- Настройка шрифтов для ReportLab (Cyrillic PDF) ---
CYRILLIC_FONT = "Helvetica"
CYRILLIC_BOLD = "Helvetica-Bold"

FONT_CANDIDATES = [
    # Linux (Debian / Ubuntu / Docker / bothost)
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    # Windows
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("C:/Windows/Fonts/calibri.ttf", "C:/Windows/Fonts/calibrib.ttf"),
]

for reg_path, bold_path in FONT_CANDIDATES:
    if os.path.exists(reg_path):
        try:
            pdfmetrics.registerFont(TTFont("CustomCyrillic", reg_path))
            CYRILLIC_FONT = "CustomCyrillic"
            if os.path.exists(bold_path):
                pdfmetrics.registerFont(TTFont("CustomCyrillicBold", bold_path))
                CYRILLIC_BOLD = "CustomCyrillicBold"
            else:
                CYRILLIC_BOLD = "CustomCyrillic"
            break
        except Exception as e:
            logger.warning("Не удалось зарегистрировать шрифт %s: %s", reg_path, e)


# ==============================================================================
# 1. Генератор Excel (.xlsx)
# ==============================================================================

def create_excel_file(data: Dict[str, Any]) -> Tuple[bytes, str]:
    """
    Генерирует форматированный Excel-файл (.xlsx) на основе переданного словаря.
    Ожидаемый формат data:
    {
        "filename": "Отчет.xlsx",
        "title": "Заголовок таблицы",  (опционально)
        "sheet": "Лист 1",            (опционально)
        "headers": ["Колонка 1", "Колонка 2", ...],
        "rows": [
            ["Значение 1", 100, ...],
            ...
        ]
    }
    """
    filename = data.get("filename", "Таблица.xlsx")
    if not filename.endswith(".xlsx"):
        filename += ".xlsx"

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = str(data.get("sheet", "Лист 1"))[:30]

    # Стили
    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    title_font = Font(name="Calibri", size=14, bold=True, color="1F4E78")
    data_font = Font(name="Calibri", size=11)
    
    thin_border = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9"),
    )
    zebra_fill = PatternFill(start_color="F2F5F9", end_color="F2F5F9", fill_type="solid")

    current_row = 1

    # Заголовок документа, если есть
    title = data.get("title")
    if title:
        ws.cell(row=current_row, column=1, value=str(title))
        ws.cell(row=current_row, column=1).font = title_font
        current_row += 2

    headers = data.get("headers", [])
    rows = data.get("rows", [])

    # Запись заголовков таблицы
    if headers:
        for col_idx, header in enumerate(headers, start=1):
            cell = ws.cell(row=current_row, column=col_idx, value=str(header))
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = thin_border
        current_row += 1

    # Запись данных
    for r_idx, row in enumerate(rows):
        is_even = (r_idx % 2 == 1)
        for c_idx, val in enumerate(row, start=1):
            # Пробуем преобразовать числовые строки в int/float для формул в Excel
            converted_val = val
            if isinstance(val, str):
                val_clean = val.replace(" ", "").replace(",", ".")
                try:
                    if "." in val_clean:
                        converted_val = float(val_clean)
                    else:
                        converted_val = int(val_clean)
                except ValueError:
                    converted_val = val

            cell = ws.cell(row=current_row, column=c_idx, value=converted_val)
            cell.font = data_font
            cell.border = thin_border
            if is_even:
                cell.fill = zebra_fill

            # Выравнивание чисел по правому краю, текста по левому
            if isinstance(converted_val, (int, float)):
                cell.alignment = Alignment(horizontal="right", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")

        current_row += 1

    # Автоподбор ширины колонок
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val_str = str(cell.value or "")
            max_len = max(max_len, len(val_str))
        ws.column_dimensions[col_letter].width = min(max(max_len + 4, 12), 50)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue(), filename


# ==============================================================================
# 2. Генератор Word (.docx)
# ==============================================================================

def create_word_file(data: Dict[str, Any]) -> Tuple[bytes, str]:
    """
    Генерирует документ Word (.docx).
    Формат data:
    {
        "filename": "Договор.docx",
        "title": "ДОГОВОР ОКАЗАНИЯ УСЛУГ",
        "subtitle": "г. Москва, 2026 г.",
        "sections": [
            {
                "heading": "1. Предмет договора",
                "paragraphs": [
                    "Исполнитель обязуется оказать услуги...",
                    "Заказчик обязуется принять и оплатить..."
                ]
            },
            ...
        ],
        "table": {  (опционально)
            "headers": ["№", "Наименование", "Сумма"],
            "rows": [["1", "Разработка", "100 000 руб."]]
        }
    }
    """
    filename = data.get("filename", "Документ.docx")
    if not filename.endswith(".docx"):
        filename += ".docx"

    doc = docx.Document()

    # Заголовок документа
    title_text = data.get("title")
    if title_text:
        title_p = doc.add_paragraph()
        title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = title_p.add_run(str(title_text))
        run.font.name = "Calibri"
        run.font.size = Pt(18)
        run.font.bold = True
        run.font.color.rgb = RGBColor(31, 78, 120)

    subtitle_text = data.get("subtitle")
    if subtitle_text:
        sub_p = doc.add_paragraph()
        sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        sub_run = sub_p.add_run(str(subtitle_text))
        sub_run.font.name = "Calibri"
        sub_run.font.size = Pt(11)
        sub_run.font.italic = True
        sub_run.font.color.rgb = RGBColor(120, 120, 120)

    # Разделы документа
    sections = data.get("sections", [])
    for sec in sections:
        heading = sec.get("heading")
        if heading:
            h = doc.add_heading(level=2)
            h_run = h.add_run(str(heading))
            h_run.font.name = "Calibri"
            h_run.font.color.rgb = RGBColor(31, 78, 120)

        for p_text in sec.get("paragraphs", []):
            p = doc.add_paragraph()
            p.paragraph_format.line_spacing = 1.15
            p.paragraph_format.space_after = Pt(6)
            run = p.add_run(str(p_text))
            run.font.name = "Calibri"
            run.font.size = Pt(11)

        for item in sec.get("bullet_points", []):
            p = doc.add_paragraph(style="List Bullet")
            p.paragraph_format.space_after = Pt(3)
            run = p.add_run(str(item))
            run.font.name = "Calibri"
            run.font.size = Pt(11)

    # Таблица внутри Word документа (если указана)
    table_data = data.get("table")
    if table_data and "headers" in table_data:
        headers = table_data.get("headers", [])
        rows = table_data.get("rows", [])
        if headers:
            table = doc.add_table(rows=1 + len(rows), cols=len(headers))
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            table.style = "Light Shading Accent 1"

            # Заголовки
            for col_idx, h in enumerate(headers):
                cell = table.cell(0, col_idx)
                cell.text = str(h)

            # Строки
            for row_idx, row in enumerate(rows, start=1):
                for col_idx, val in enumerate(row):
                    cell = table.cell(row_idx, col_idx)
                    cell.text = str(val)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue(), filename


# ==============================================================================
# 3. Генератор презентаций в PDF
# ==============================================================================

def create_pdf_presentation(data: Dict[str, Any]) -> Tuple[bytes, str]:
    """
    Генерирует стильную презентацию в формате PDF (альбомная ориентация A4).
    Формат data:
    {
        "filename": "Презентация.pdf",
        "title": "Заголовок презентации",
        "subtitle": "Подзаголовок или автор",
        "slides": [
            {
                "title": "1. Проблема",
                "points": ["Описание пункта 1", "Описание пункта 2"]
            },
            {
                "title": "2. Наше решение",
                "points": ["Пункт решения А", "Пункт решения Б"]
            }
        ]
    }
    """
    filename = data.get("filename", "Презентация.pdf")
    if not filename.endswith(".pdf"):
        filename += ".pdf"

    buf = io.BytesIO()
    page_w, page_h = landscape(A4)
    c = canvas.Canvas(buf, pagesize=(page_w, page_h))

    slides = data.get("slides", [])
    title = data.get("title", "Презентация")
    subtitle = data.get("subtitle", "")

    total_slides = max(1 + len(slides), 1)

    # --- Слайд 1: Титульный слайд ---
    # Градиентный или стильный темно-синий фон
    c.setFillColor(colors.HexColor("#1A365D"))
    c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

    # Декоративная акцентная полоса
    c.setFillColor(colors.HexColor("#3182CE"))
    c.rect(0, page_h - 15, page_w, 15, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#63B3ED"))
    c.rect(0, 0, page_w, 10, fill=1, stroke=0)

    # Заголовок
    c.setFillColor(colors.white)
    c.setFont(CYRILLIC_BOLD, 32)
    c.drawCentredString(page_w / 2, page_h / 2 + 30, title)

    # Подзаголовок
    if subtitle:
        c.setFillColor(colors.HexColor("#E2E8F0"))
        c.setFont(CYRILLIC_FONT, 18)
        c.drawCentredString(page_w / 2, page_h / 2 - 25, subtitle)

    c.showPage()

    # --- Слайды 2..N: Слайды с контентом ---
    for s_idx, slide in enumerate(slides, start=2):
        s_title = slide.get("title", f"Слайд {s_idx - 1}")
        points = slide.get("points", [])

        # Светлый фон
        c.setFillColor(colors.HexColor("#F8FAFC"))
        c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

        # Верхняя шапка слайда
        c.setFillColor(colors.HexColor("#1E3A8A"))
        c.rect(0, page_h - 80, page_w, 80, fill=1, stroke=0)

        # Заголовок слайда
        c.setFillColor(colors.white)
        c.setFont(CYRILLIC_BOLD, 22)
        c.drawString(40, page_h - 52, s_title)

        # Номер слайда внизу
        c.setFillColor(colors.HexColor("#64748B"))
        c.setFont(CYRILLIC_FONT, 10)
        c.drawRightString(page_w - 40, 25, f"Слайд {s_idx} из {total_slides}")

        # Декоративная линия подвала
        c.setStrokeColor(colors.HexColor("#CBD5E1"))
        c.setLineWidth(1)
        c.line(40, 45, page_w - 40, 45)

        # Вывод пунктов слайда (bullet points)
        current_y = page_h - 130
        line_height = 36

        c.setFont(CYRILLIC_FONT, 15)
        c.setFillColor(colors.HexColor("#1E293B"))

        for pt in points:
            if current_y < 70:
                break
            # Рисуем стильный маркер-кружок
            c.setFillColor(colors.HexColor("#2563EB"))
            c.circle(55, current_y + 5, 4, fill=1, stroke=0)

            # Текст пункта (с разбивкой длинных строк)
            c.setFillColor(colors.HexColor("#1E293B"))
            pt_str = str(pt)
            
            # Простой перенос длинных строк
            words = pt_str.split()
            current_line = []
            for w in words:
                test_line = " ".join(current_line + [w])
                if c.stringWidth(test_line, CYRILLIC_FONT, 15) < (page_w - 120):
                    current_line.append(w)
                else:
                    c.drawString(75, current_y, " ".join(current_line))
                    current_y -= 22
                    current_line = [w]

            if current_line:
                c.drawString(75, current_y, " ".join(current_line))
                current_y -= line_height

        c.showPage()

    c.save()
    buf.seek(0)
    return buf.getvalue(), filename


# ==============================================================================
# 4. Парсер структурированных блоков и генератор файлов
# ==============================================================================

EXCEL_PATTERN = re.compile(r"```(?:excel:data|excel|table:data)\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)
DOC_PATTERN = re.compile(r"```(?:doc:data|word:data|docx:data|doc)\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)
PRESENTATION_PATTERN = re.compile(r"```(?:presentation:data|pdf:presentation|slides:data|presentation)\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


def extract_and_generate_files(raw_text: str) -> Tuple[str, List[Tuple[bytes, str]]]:
    """
    Анализирует текст ответа модели.
    Если находит специальные блоки (excel, doc, presentation), генерирует файлы.
    Возвращает:
        (очищенный_текст_сообщения, список_файлов: [(bytes, filename), ...])
    """
    cleaned_text = raw_text
    files: List[Tuple[bytes, str]] = []

    # 1. Извлечение Excel
    for match in EXCEL_PATTERN.finditer(raw_text):
        json_str = match.group(1).strip()
        try:
            data = json.loads(json_str)
            file_bytes, filename = create_excel_file(data)
            files.append((file_bytes, filename))
            cleaned_text = cleaned_text.replace(match.group(0), "").strip()
        except Exception as e:
            logger.warning("Ошибка парсинга блока Excel: %s", e)

    # 2. Извлечение Word
    for match in DOC_PATTERN.finditer(raw_text):
        json_str = match.group(1).strip()
        try:
            data = json.loads(json_str)
            file_bytes, filename = create_word_file(data)
            files.append((file_bytes, filename))
            cleaned_text = cleaned_text.replace(match.group(0), "").strip()
        except Exception as e:
            logger.warning("Ошибка парсинга блока Word: %s", e)

    # 3. Извлечение Презентации
    for match in PRESENTATION_PATTERN.finditer(raw_text):
        json_str = match.group(1).strip()
        try:
            data = json.loads(json_str)
            file_bytes, filename = create_pdf_presentation(data)
            files.append((file_bytes, filename))
            cleaned_text = cleaned_text.replace(match.group(0), "").strip()
        except Exception as e:
            logger.warning("Ошибка парсинга блока Презентации: %s", e)

    return cleaned_text, files
