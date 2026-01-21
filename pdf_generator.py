from weasyprint import HTML
from jinja2 import Environment, FileSystemLoader
from datetime import datetime, timedelta
from num2words import num2words
import os

from config import COMPANY, PAYMENT_DAYS


def number_to_words_ru(number: float) -> str:
    """Преобразование числа в сумму прописью на русском"""
    rubles = int(number)
    kopeks = int(round((number - rubles) * 100))
    
    rubles_word = num2words(rubles, lang='ru')
    
    # Определяем форму слова "рубль"
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
    
    # Форма слова "копейка"
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
    
    # Загружаем шаблон
    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("invoice.html")
    
    # Подготавливаем данные
    invoice_date = datetime.fromisoformat(order["created_at"].replace("Z", ""))
    payment_date = invoice_date + timedelta(days=PAYMENT_DAYS)
    
    total_amount = order["total_amount"]
    total_words = number_to_words_ru(total_amount)
    
    # Рендерим HTML
    html_content = template.render(
        invoice_number=order["invoice_number"],
        invoice_date=invoice_date.strftime("%d.%m.%Y"),
        payment_date=payment_date.strftime("%d.%m.%Y"),
        
        seller=COMPANY,
        
        buyer={
            "name": order["company_name"],
            "inn": order["company_inn"],
            "kpp": order["company_kpp"] or "",
            "address": order["company_address"],
        },
        
        products=order["products"],
        total_amount=f"{total_amount:,.2f}".replace(",", " ").replace(".", ","),
        total_words=total_words,
    )
    
    # Генерируем PDF
    pdf_bytes = HTML(string=html_content).write_pdf()
    
    return pdf_bytes
