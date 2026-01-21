from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from datetime import datetime
import json

from database import (
    init_db, create_order, get_order, get_all_orders,
    update_order_company, mark_pdf_generated
)
from dadata_client import get_company_by_inn
from pdf_generator import generate_invoice_pdf
from config import COMPANY, INVOICE_PREFIX, INVOICE_START_NUMBER

app = FastAPI(title="InvoiceGen")

# Статические файлы и шаблоны
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Инициализация БД при запуске
@app.on_event("startup")
async def startup():
    init_db()


# ============== ВЕБХУК ОТ ТИЛЬДЫ ==============

@app.post("/webhook/tilda")
async def tilda_webhook(request: Request):
    """Приём заказа от Тильды"""
    
    # Тильда отправляет данные как form-data
    form_data = await request.form()
    data = dict(form_data)
    
    # Также может прийти как JSON
    if not data:
        try:
            data = await request.json()
        except:
            pass
    
    print("Received from Tilda:", data)
    
    # Парсим товары из Тильды
    products = []
    total_amount = 0
    
    # Тильда передаёт товары в формате payment[products][0][name], и т.д.
    # Или в массиве products
    
    # Вариант 1: Данные в формате payment[products]
    i = 0
    while True:
        name_key = f"payment[products][{i}][name]"
        if name_key in data:
            product = {
                "name": data.get(f"payment[products][{i}][name]", ""),
                "quantity": int(data.get(f"payment[products][{i}][quantity]", 1)),
                "price": float(data.get(f"payment[products][{i}][price]", 0)),
                "period": data.get(f"payment[products][{i}][options]", ""),  # Срок из опций
            }
            product["amount"] = product["quantity"] * product["price"]
            total_amount += product["amount"]
            products.append(product)
            i += 1
        else:
            break
    
    # Вариант 2: Простой формат
    if not products and "Name" in data:
        product = {
            "name": data.get("Name", "Услуга"),
            "quantity": int(data.get("Quantity", 1)),
            "price": float(data.get("Price", 0)),
            "period": data.get("Period", ""),
        }
        product["amount"] = product["quantity"] * product["price"]
        total_amount = product["amount"]
        products.append(product)
    
    # Если товары не распознаны, создаём заглушку
    if not products:
        products = [{
            "name": "Услуга (данные не распознаны)",
            "quantity": 1,
            "price": float(data.get("payment[amount]", 0) or data.get("Amount", 0) or 0),
            "period": "",
        }]
        products[0]["amount"] = products[0]["price"]
        total_amount = products[0]["amount"]
    
    # Данные клиента
    customer_name = data.get("Name", "") or data.get("name", "") or data.get("payment[name]", "")
    customer_email = data.get("Email", "") or data.get("email", "") or data.get("payment[email]", "")
    customer_phone = data.get("Phone", "") or data.get("phone", "") or data.get("payment[phone]", "")
    
    # Создаём заказ
    order_id = create_order(
        products=products,
        total_amount=total_amount,
        customer_name=customer_name,
        customer_email=customer_email,
        customer_phone=customer_phone,
        invoice_prefix=INVOICE_PREFIX,
        start_number=INVOICE_START_NUMBER
    )
    
    return {
        "success": True,
        "order_id": order_id,
        "form_url": f"/order/{order_id}"
    }


# ============== ФОРМА ДОЗАПОЛНЕНИЯ ==============

@app.get("/order/{order_id}", response_class=HTMLResponse)
async def order_form(request: Request, order_id: int):
    """Страница с формой дозаполнения реквизитов"""
    
    order = get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    
    return templates.TemplateResponse("order_form.html", {
        "request": request,
        "order": order,
        "seller": COMPANY,
    })


@app.get("/api/company")
async def api_get_company(inn: str):
    """API для получения данных компании по ИНН"""
    
    company = await get_company_by_inn(inn)
    if company:
        return company
    return {"error": "Компания не найдена"}


@app.post("/order/{order_id}/save")
async def save_order_company(
    order_id: int,
    company_name: str = Form(...),
    company_inn: str = Form(...),
    company_kpp: str = Form(""),
    company_address: str = Form(...)
):
    """Сохранение реквизитов компании"""
    
    order = get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    
    update_order_company(
        order_id=order_id,
        company_name=company_name,
        company_inn=company_inn,
        company_kpp=company_kpp,
        company_address=company_address
    )
    
    return RedirectResponse(url=f"/order/{order_id}/preview", status_code=303)


# ============== ГЕНЕРАЦИЯ PDF ==============

@app.get("/order/{order_id}/preview", response_class=HTMLResponse)
async def order_preview(request: Request, order_id: int):
    """Предпросмотр перед генерацией PDF"""
    
    order = get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    
    if not order["company_inn"]:
        return RedirectResponse(url=f"/order/{order_id}")
    
    return templates.TemplateResponse("preview.html", {
        "request": request,
        "order": order,
        "seller": COMPANY,
    })


@app.get("/order/{order_id}/download")
async def download_pdf(order_id: int):
    """Скачивание PDF счёта"""
    
    order = get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    
    if not order["company_inn"]:
        raise HTTPException(status_code=400, detail="Сначала заполните реквизиты")
    
    pdf_bytes = generate_invoice_pdf(order)
    mark_pdf_generated(order_id)
    
    filename = f"Invoice_{order['invoice_number']}.pdf"
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


# ============== АДМИНКА ==============

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request):
    """Админ-панель со списком заказов"""
    
    orders = get_all_orders()
    
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "orders": orders,
    })


# ============== ГЛАВНАЯ ==============

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Главная страница"""
    return RedirectResponse(url="/admin")
