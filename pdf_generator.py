from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from datetime import datetime, timedelta
from num2words import num2words
from io import BytesIO

from config import COMPANY, PAYMENT_DAYS


def number_to_words_ru(number: float) -> str:
    """Преобразование числа в сумму прописью на русском"""
    rubles = int(number)
    kopeks = int(round((number - rubles) * 100))
    
    rubles_word = num2words(rubles, lang='ru')
    
    last_two = rubles % 100
    last_one = rubles % 10
    
    if 11 <= last_two <= 19:
        rub_form = "рублей"
    elif last_one == 1:
        rub_form = "рубль"
    elif 2 <= last_one <= 4:
        rub_form = "рубля"
    else:
        rub_form = "рублей"
    
    kop_last_two = kopeks % 100
    kop_last_one = kopeks % 10
    
    if 11 <= kop_last_two <= 19:
        kop_form = "копеек"
    elif kop_last_one == 1:
        kop_form = "копейка"
    elif 2 <= kop_last_one <= 4:
        kop_form = "копейки"
    else:
        kop_form = "копеек"
    
    return f"{rubles_word.capitalize()} {rub_form} {kopeks:02d} {kop_form}"


def generate_invoice_pdf(order: dict) -> bytes:
    """Генерация PDF счёта-оферты"""
    
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # Подготавливаем данные
    created_at = order["created_at"]
    if isinstance(created_at, str):
        invoice_date = datetime.fromisoformat(created_at.replace("Z", "").split(".")[0])
    else:
        invoice_date = created_at
    
    payment_date = invoice_date + timedelta(days=PAYMENT_DAYS)
    total_amount = order["total_amount"]
    total_words = number_to_words_ru(total_amount)
    
    # Начальная позиция
    y = height - 30*mm
    left_margin = 20*mm
    
    # === ШАПКА С РЕКВИЗИТАМИ БАНКА ===
    c.setFont("Helvetica-Bold", 10)
    c.drawString(left_margin, y, "Poluchatel:")
    y -= 5*mm
    
    c.setFont("Helvetica", 9)
    c.drawString(left_margin, y, f"INN {COMPANY['inn']} KPP {COMPANY['kpp']}")
    y -= 4*mm
    c.drawString(left_margin, y, f"{COMPANY['name']}")
    y -= 4*mm
    c.drawString(left_margin, y, f"R/Sch. No {COMPANY['account']}")
    y -= 6*mm
    
    c.setFont("Helvetica-Bold", 10)
    c.drawString(left_margin, y, "Bank poluchatelya:")
    y -= 5*mm
    
    c.setFont("Helvetica", 9)
    c.drawString(left_margin, y, f"{COMPANY['bank_name']}")
    y -= 4*mm
    c.drawString(left_margin, y, f"BIK {COMPANY['bik']} K/Sch. No {COMPANY['corr_account']}")
    y -= 10*mm
    
    # === ЗАГОЛОВОК СЧЁТА ===
    c.setFont("Helvetica-Bold", 14)
    title = f"Schet-oferta {order['invoice_number']} ot {invoice_date.strftime('%d.%m.%Y')}"
    c.drawCentredString(width/2, y, title)
    y -= 10*mm
    
    # === СТОРОНЫ ===
    c.setFont("Helvetica-Bold", 9)
    c.drawString(left_margin, y, "Agent:")
    c.setFont("Helvetica", 9)
    c.drawString(left_margin + 15*mm, y, f"{COMPANY['name']}, INN: {COMPANY['inn']}, KPP: {COMPANY['kpp']}")
    y -= 4*mm
    c.drawString(left_margin, y, f"Adres: {COMPANY['address']}")
    y -= 4*mm
    c.drawString(left_margin, y, f"Tel.: {COMPANY['phone']}, Email: {COMPANY['email']}")
    y -= 6*mm
    
    c.setFont("Helvetica-Bold", 9)
    c.drawString(left_margin, y, "Klient:")
    c.setFont("Helvetica", 9)
    kpp_text = f", KPP: {order['company_kpp']}" if order.get("company_kpp") else ""
    c.drawString(left_margin + 15*mm, y, f"{order['company_name']}, INN: {order['company_inn']}{kpp_text}")
    y -= 4*mm
    
    if order.get("company_address"):
        c.drawString(left_margin, y, f"Adres: {order['company_address'][:80]}")
        y -= 4*mm
    
    y -= 2*mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(left_margin, y, f"Srok oplaty: {payment_date.strftime('%d.%m.%Y')}")
    y -= 8*mm
    
    # === ТАБЛИЦА ТОВАРОВ ===
    c.setFont("Helvetica-Bold", 9)
    
    # Заголовки таблицы
    col_x = [left_margin, left_margin + 10*mm, left_margin + 100*mm, left_margin + 140*mm]
    
    c.setFillColor(colors.lightgrey)
    c.rect(left_margin, y - 2*mm, 170*mm, 7*mm, fill=True, stroke=True)
    c.setFillColor(colors.black)
    
    c.drawString(col_x[0] + 2*mm, y, "No")
    c.drawString(col_x[1] + 2*mm, y, "Naimenovanie")
    c.drawString(col_x[2] + 2*mm, y, "Period")
    c.drawString(col_x[3] + 2*mm, y, "Summa, rub.")
    y -= 7*mm
    
    # Строки товаров
    c.setFont("Helvetica", 9)
    for idx, product in enumerate(order["products"], 1):
        c.rect(left_margin, y - 2*mm, 170*mm, 6*mm, fill=False, stroke=True)
        c.drawString(col_x[0] + 2*mm, y, str(idx))
        
        name = product["name"][:45] if len(product["name"]) > 45 else product["name"]
        c.drawString(col_x[1] + 2*mm, y, name)
        c.drawString(col_x[2] + 2*mm, y, product.get("period", "-") or "-")
        c.drawString(col_x[3] + 2*mm, y, f"{product['amount']:,.2f}".replace(",", " "))
        y -= 6*mm
    
    # НДС
    y -= 2*mm
    c.drawString(col_x[2] + 2*mm, y, "NDS:")
    c.drawString(col_x[3] + 2*mm, y, "Bez NDS")
    y -= 5*mm
    
    # ИТОГО
    c.setFont("Helvetica-Bold", 10)
    c.drawString(col_x[2] + 2*mm, y, "ITOGO:")
    c.drawString(col_x[3] + 2*mm, y, f"{total_amount:,.2f}".replace(",", " "))
    y -= 8*mm
    
    # === СУММА ПРОПИСЬЮ ===
    c.setFont("Helvetica-Bold", 9)
    c.drawString(left_margin, y, f"Vsego k oplate: {total_words}")
    y -= 10*mm
    
    # === УСЛОВИЯ ОФЕРТЫ ===
    c.setFont("Helvetica", 7)
    terms = [
        "Nastoyaschiy Schet-oferta yavlyaetsya pismennym predlozheniem (ofertoy) Agenta zaklyuchit Dogovor",
        "v sootvetstvii so st. 432-444 GK RF. Dogovor zaklyuchaetsya putem prinyatiya (aktsepta) oferty Klientom.",
        "",
        "1. Predmet Dogovora.",
        "1.1. Po nastoyaschemu dogovoru Agent obyazuetsya okazat uslugi, perechislennye v Schete, a Klient obyazuetsya oplatit eti uslugi.",
        "",
        "2. Poryadok raschetov.",
        "2.1. Klient obyazuetsya oplatit Schet-ofertu v techenie 3-h rabochih dney s momenta polucheniya.",
        "2.2. Obyazannost Klienta po oplate schitaetsya ispolnennoy s momenta postupleniya denezhnyh sredstv na raschetnyy schet Agenta.",
        "",
        "3. Srok deystviya Dogovora.",
        "3.1. Dogovor vstupaet v deystvie s momenta aktsepta (oplaty Scheta-oferty) do momenta vypolneniya uslug.",
    ]
    
    for line in terms:
        if y < 20*mm:
            c.showPage()
            y = height - 20*mm
            c.setFont("Helvetica", 7)
        c.drawString(left_margin, y, line)
        y -= 3.5*mm
    
    c.save()
    
    buffer.seek(0)
    return buffer.getvalue()
