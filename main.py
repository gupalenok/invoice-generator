from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
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
# Разрешаем запросы от Тильды
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Статические файлы и шаблоны
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Инициализация БД при запуске
@app.on_event("startup")
async def startup():
    init_db()



# Парсер

def parse_tilda_order(data: dict) -> dict:
    """Парсит данные заказа от Тильды (form-data формат)"""
    
    # Извлекаем товары из формата payment[products][0][name]
    products = []
    i = 0
    while True:
        name_key = f'payment[products][{i}][name]'
        if name_key not in data:
            break
        
        product = {
            "name": data.get(f'payment[products][{i}][name]', ''),
            "quantity": int(data.get(f'payment[products][{i}][quantity]', 1)),
            "price": float(data.get(f'payment[products][{i}][price]', 0)),
            "amount": float(data.get(f'payment[products][{i}][amount]', 0)),
            "sku": data.get(f'payment[products][{i}][sku]', ''),
            "period": "",  # Можно извлечь из названия если нужно
        }
        products.append(product)
        i += 1
    
    # Если товары не найдены, создаём один товар из общей суммы
    if not products:
        total = float(data.get('payment[amount]', 0))
        if total > 0:
            products = [{
                "name": "Заказ",
                "quantity": 1,
                "price": total,
                "amount": total,
                "sku": "",
                "period": "",
            }]
    
    # Общая сумма
    total_amount = float(data.get('payment[amount]', 0))
    if total_amount == 0:
        total_amount = sum(p['amount'] for p in products)
    
    # Номер заказа
    order_id = data.get('payment[orderid]', '')
    
    return {
        "tilda_order_id": order_id,
        "customer_name": data.get('Name', ''),
        "customer_email": data.get('Email', ''),
        "customer_phone": data.get('Phone', ''),
        "products": products,
        "total_amount": total_amount,
    }




# ============== ВЕБХУК ОТ ТИЛЬДЫ ==============

@app.post("/webhook/tilda")
async def tilda_webhook(request: Request):
    """Приём вебхука от Тильды"""
    try:
        content_type = request.headers.get("content-type", "")
        
        print("=" * 50)
        print("WEBHOOK RECEIVED!")
        print(f"Content-Type: {content_type}")
        
        # Получаем form-data
        data = {}
        try:
            form_data = await request.form()
            data = dict(form_data)
        except:
            pass
        
        if not data:
            try:
                data = await request.json()
            except:
                pass
        
        if not data:
            print("No data received")
            return {"status": "error", "message": "No data received"}
        
        print(f"Data: {data}")
        
        # Парсим заказ
        order_data = parse_tilda_order(data)
        print(f"Parsed order: {order_data}")
        
        # Сохраняем - передаём параметры правильно
        order_id = create_order(
            products=order_data["products"],
            total_amount=order_data["total_amount"],
            customer_name=order_data["customer_name"],
            customer_email=order_data["customer_email"],
            customer_phone=order_data["customer_phone"],
            invoice_prefix="СЧ",
            start_number=1
        )
        
        print(f"SUCCESS! Created order ID: {order_id}")
        print("=" * 50)
        
        return {"status": "ok", "order_id": order_id}
        
    except Exception as e:
        import traceback
        print(f"WEBHOOK ERROR: {traceback.format_exc()}")
        return {"status": "ok"}





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
    try:
        orders = get_all_orders()
        return templates.TemplateResponse("admin.html", {
            "request": request,
            "orders": orders,
        })
    except Exception as e:
        import traceback
        error_text = traceback.format_exc()
        print(f"ERROR in /admin: {error_text}")
        return HTMLResponse(content=f"<pre>Error: {error_text}</pre>", status_code=500)



# ============== ГЛАВНАЯ ==============

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Главная страница"""
    return RedirectResponse(url="/admin")

def update_order_company(order_id: int, company_name: str, company_inn: str, 
                          company_kpp: str, company_address: str) -> bool:
    """Обновление данных компании в заказе"""
    return update_order(order_id, {
        "company_name": company_name,
        "company_inn": company_inn,
        "company_kpp": company_kpp,
        "company_address": company_address
    })

