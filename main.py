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
    """Приём вебхука от Тильды"""
    try:
        # Получаем данные
        content_type = request.headers.get("content-type", "")
        
        if "application/json" in content_type:
            data = await request.json()
        else:
            form_data = await request.form()
            data = dict(form_data)
        
        # ЛОГИРУЕМ ВСЁ ЧТО ПРИШЛО
        print("=" * 50)
        print("WEBHOOK RECEIVED!")
        print(f"Content-Type: {content_type}")
        print(f"Data: {data}")
        print("=" * 50)
        
        # Парсим заказ
        order_data = parse_tilda_order(data)
        
        print(f"Parsed order: {order_data}")
        
        # Сохраняем
        order_id = create_order(order_data)
        
        print(f"Created order ID: {order_id}")
        
        return {"status": "ok", "order_id": order_id}
        
    except Exception as e:
        import traceback
        error_text = traceback.format_exc()
        print(f"WEBHOOK ERROR: {error_text}")
        return {"status": "error", "message": str(e)}




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
