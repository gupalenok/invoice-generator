from fpdf import FPDF
from datetime import datetime, timedelta
from num2words import num2words
import os

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


class InvoicePDF(FPDF):
    def __init__(self):
        super().__init__()
        # Добавляем поддержку русского языка
        self.add_font('DejaVu', '', 'fonts/DejaVuSans.ttf', uni=True)
        self.add_font('DejaVu', 'B', 'fonts/DejaVuSans-Bold.ttf', uni=True)
        
    def header(self):
        pass
        
    def footer(self):
        self.set_y(-15)
        self.set_font('DejaVu', '', 8)
        self.cell(0, 10, f'Страница {self.page_no()}', 0, 0, 'C')


def generate_invoice_pdf(order: dict) -> bytes:
    """Генерация PDF счёта-оферты"""
    
    # Создаём PDF
    pdf = FPDF()
    pdf.add_page()
    
    # Добавляем встроенный шрифт с поддержкой кириллицы
    pdf.add_font('DejaVu', '', 'https://github.com/ArtifexSoftware/urern-fonts/raw/main/DejaVuSans.ttf', uni=True)
    
    # Подготавливаем данные
    created_at = order["created_at"]
    if isinstance(created_at, str):
        invoice_date = datetime.fromisoformat(created_at.replace("Z", "").split(".")[0])
    else:
        invoice_date = created_at
    
    payment_date = invoice_date + timedelta(days=PAYMENT_DAYS)
    
    total_amount = order["total_amount"]
    total_words = number_to_words_ru(total_amount)
    
    # === ШАПКА С РЕКВИЗИТАМИ БАНКА ===
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(0, 6, 'Получатель:', 0, 1)
    
    pdf.set_font('Helvetica', '', 9)
    pdf.cell(0, 5, f'ИНН {COMPANY["inn"]} КПП {COMPANY["kpp"]}', 0, 1)
    pdf.cell(0, 5, f'{COMPANY["name"]}', 0, 1)
    pdf.cell(0, 5, f'Р/Сч. № {COMPANY["account"]}', 0, 1)
    
    pdf.ln(3)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(0, 6, 'Банк получателя:', 0, 1)
    
    pdf.set_font('Helvetica', '', 9)
    pdf.cell(0, 5, f'{COMPANY["bank_name"]}', 0, 1)
    pdf.cell(0, 5, f'БИК {COMPANY["bik"]} К/Сч. № {COMPANY["corr_account"]}', 0, 1)
    
    # === ЗАГОЛОВОК СЧЁТА ===
    pdf.ln(10)
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 10, f'Счёт-оферта {order["invoice_number"]} от {invoice_date.strftime("%d.%m.%Y")}', 0, 1, 'C')
    
    # === СТОРОНЫ ===
    pdf.ln(5)
    pdf.set_font('Helvetica', '', 9)
    
    # Агент
    pdf.set_font('Helvetica', 'B', 9)
    pdf.cell(15, 5, 'Агент:', 0, 0)
    pdf.set_font('Helvetica', '', 9)
    agent_text = f'{COMPANY["name_full"]}, ИНН: {COMPANY["inn"]}, КПП: {COMPANY["kpp"]}'
    pdf.multi_cell(0, 5, agent_text)
    
    pdf.cell(0, 5, f'Адрес: {COMPANY["address"]}', 0, 1)
    pdf.cell(0, 5, f'Тел.: {COMPANY["phone"]}, Email: {COMPANY["email"]}', 0, 1)
    
    pdf.ln(3)
    
    # Клиент
    pdf.set_font('Helvetica', 'B', 9)
    pdf.cell(15, 5, 'Клиент:', 0, 0)
    pdf.set_font('Helvetica', '', 9)
    
    kpp_text = f', КПП: {order["company_kpp"]}' if order.get("company_kpp") else ''
    client_text = f'{order["company_name"]}, ИНН: {order["company_inn"]}{kpp_text}'
    pdf.multi_cell(0, 5, client_text)
    
    if order.get("company_address"):
        pdf.cell(0, 5, f'Адрес: {order["company_address"]}', 0, 1)
    
    pdf.ln(2)
    pdf.set_font('Helvetica', 'B', 9)
    pdf.cell(0, 5, f'Срок оплаты: {payment_date.strftime("%d.%m.%Y")}', 0, 1)
    
    # === ТАБЛИЦА ТОВАРОВ ===
    pdf.ln(5)
    
    # Заголовок таблицы
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_fill_color(240, 240, 240)
    
    col_widths = [10, 90, 40, 50]
    headers = ['№', 'Наименование', 'Период', 'Стоимость, руб.']
    
    for i, header in enumerate(headers):
        pdf.cell(col_widths[i], 8, header, 1, 0, 'C', True)
    pdf.ln()
    
    # Строки товаров
    pdf.set_font('Helvetica', '', 9)
    
    for idx, product in enumerate(order["products"], 1):
        pdf.cell(col_widths[0], 7, str(idx), 1, 0, 'C')
        pdf.cell(col_widths[1], 7, product["name"][:50], 1, 0, 'L')
        pdf.cell(col_widths[2], 7, product.get("period", "-") or "-", 1, 0, 'C')
        pdf.cell(col_widths[3], 7, f'{product["amount"]:,.2f}'.replace(",", " "), 1, 0, 'R')
        pdf.ln()
    
    # НДС
    pdf.set_font('Helvetica', '', 9)
    pdf.cell(col_widths[0] + col_widths[1], 7, '', 0, 0)
    pdf.cell(col_widths[2], 7, 'НДС:', 0, 0, 'R')
    pdf.cell(col_widths[3], 7, 'Без НДС', 1, 1, 'R')
    
    # ИТОГО
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(col_widths[0] + col_widths[1], 8, '', 0, 0)
    pdf.cell(col_widths[2], 8, 'ИТОГО:', 0, 0, 'R')
    pdf.cell(col_widths[3], 8, f'{total_amount:,.2f}'.replace(",", " "), 1, 1, 'R')
    
    # === СУММА ПРОПИСЬЮ ===
    pdf.ln(5)
    pdf.set_font('Helvetica', 'B', 9)
    pdf.cell(0, 6, f'Всего к оплате: {total_words}', 0, 1)
    
    # === УСЛОВИЯ ОФЕРТЫ ===
    pdf.ln(5)
    pdf.set_font('Helvetica', '', 8)
    
    terms = """Настоящий Счёт-оферта является письменным предложением (офертой) Агента заключить Договор в соответствии со ст. 432-444 ГК РФ. Договор заключается путем принятия (акцепта) оферты Клиентом (п. 3 ст. 438 ГК РФ).

1. Предмет Договора.
1.1. По настоящему договору Агент обязуется оказать услуги, перечисленные в Счёте, а Клиент обязуется оплатить эти услуги.

2. Порядок расчетов.
2.1. Клиент обязуется оплатить Счёт-оферту в течение 3-х рабочих дней с момента получения.
2.2. Обязанность Клиента по оплате считается исполненной с момента поступления денежных средств на расчетный счет Агента.

3. Срок действия Договора.
3.1. Договор вступает в действие с момента акцепта (оплаты Счета-оферты) до момента выполнения услуг."""
    
    pdf.multi_cell(0, 4, terms)
    
    # Возвращаем PDF как bytes
    return pdf.output()
