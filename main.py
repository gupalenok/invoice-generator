# ============== ВЕБХУК ОТ ТИЛЬДЫ ==============

@app.post("/webhook/tilda")
async def tilda_webhook(request: Request):
    """Приём заказа от Тильды"""
    
    # Тильда отправляет данные как form-data
    form_data = await request.form()
    data = dict(form_data)
    
    # Тестовый запрос от Тильды — просто отвечаем OK
    if data.get("test") == "test":
        return {"success": True, "message": "Webhook is working"}
    
    # Также может прийти как JSON
    if not data:
        try:
            data = await request.json()
        except:
            pass
    
    # Если данных нет — возвращаем успех (для любых тестовых запросов)
    if not data:
        return {"success": True}
    
    print("Received from Tilda:", data)
    
    # Парсим товары из Тильды
    products = []
    total_amount = 0
    
    # Вариант 1: Данные в формате payment[products][0][name]
    i = 0
    while True:
        name_key = f"payment[products][{i}][name]"
        if name_key in data:
            product = {
                "name": data.get(f"payment[products][{i}][name]", ""),
                "quantity": int(data.get(f"payment[products][{i}][quantity]", 1) or 1),
                "price": float(data.get(f"payment[products][{i}][price]", 0) or 0),
                "period": data.get(f"payment[products][{i}][options]", ""),
            }
            product["amount"] = product["quantity"] * product["price"]
            total_amount += product["amount"]
            products.append(product)
            i += 1
        else:
            break
    
    # Вариант 2: Простой формат
    if not products and data.get("Name"):
        product = {
            "name": data.get("Name", "Услуга"),
            "quantity": int(data.get("Quantity", 1) or 1),
            "price": float(data.get("Price", 0) or 0),
            "period": data.get("Period", ""),
        }
        product["amount"] = product["quantity"] * product["price"]
        total_amount = product["amount"]
        products.append(product)
    
    # Вариант 3: Формат с payment[amount]
    if not products:
        amount = data.get("payment[amount]") or data.get("Amount") or data.get("amount") or 0
        if amount:
            products = [{
                "name": data.get("payment[products][0][name]", "Услуга"),
                "quantity": 1,
                "price": float(amount),
                "period": "",
                "amount": float(amount),
            }]
            total_amount = float(amount)
    
    # Если всё ещё нет товаров — не создаём заказ
    if not products or total_amount == 0:
        return {"success": True, "message": "No products found, order not created"}
    
    # Данные клиента
    customer_name = (
        data.get("Name") or 
        data.get("name") or 
        data.get("payment[name]") or 
        ""
    )
    customer_email = (
        data.get("Email") or 
        data.get("email") or 
        data.get("payment[email]") or 
        ""
    )
    customer_phone = (
        data.get("Phone") or 
        data.get("phone") or 
        data.get("payment[phone]") or 
        ""
    )
    
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
