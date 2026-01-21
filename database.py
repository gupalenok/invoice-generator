import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from typing import Optional
import json

DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    """Подключение к PostgreSQL"""
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def init_db():
    """Создание таблиц"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            invoice_number TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'new',
            
            products TEXT,
            total_amount REAL,
            
            customer_name TEXT,
            customer_email TEXT,
            customer_phone TEXT,
            
            company_name TEXT,
            company_inn TEXT,
            company_kpp TEXT,
            company_address TEXT
        )
    """)
    
    conn.commit()
    conn.close()
    print("Database initialized!")


def get_next_invoice_number(prefix: str = "СЧ", start_number: int = 1) -> str:
    """Генерация номера счёта"""
    conn = get_connection()
    cursor = conn.cursor()
    
    today = datetime.now().strftime("%Y%m%d")
    
    cursor.execute(
        "SELECT COUNT(*) as cnt FROM orders WHERE invoice_number LIKE %s",
        (f"{prefix}-{today}%",)
    )
    result = cursor.fetchone()
    count = result['cnt'] if result else 0
    
    conn.close()
    
    number = start_number + count
    return f"{prefix}-{today}-{number:03d}"


def create_order(
    products: list,
    total_amount: float,
    customer_name: str,
    customer_email: str,
    customer_phone: str,
    invoice_prefix: str = "СЧ",
    start_number: int = 1
) -> int:
    """Создание заказа"""
    conn = get_connection()
    cursor = conn.cursor()
    
    invoice_number = get_next_invoice_number(invoice_prefix, start_number)
    
    cursor.execute("""
        INSERT INTO orders (
            invoice_number, products, total_amount,
            customer_name, customer_email, customer_phone
        ) VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (
        invoice_number,
        json.dumps(products, ensure_ascii=False),
        total_amount,
        customer_name,
        customer_email,
        customer_phone
    ))
    
    order_id = cursor.fetchone()['id']
    conn.commit()
    conn.close()
    
    print(f"Created order {order_id}: {invoice_number}")
    return order_id


def get_order(order_id: int) -> Optional[dict]:
    """Получение заказа по ID"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        order = dict(row)
        order["products"] = json.loads(order["products"]) if order["products"] else []
        return order
    return None


def get_all_orders() -> list:
    """Получение всех заказов"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM orders ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    
    orders = []
    for row in rows:
        order = dict(row)
        order["products"] = json.loads(order["products"]) if order["products"] else []
        orders.append(order)
    
    return orders


def update_order(order_id: int, data: dict) -> bool:
    """Обновление заказа"""
    conn = get_connection()
    cursor = conn.cursor()
    
    fields = []
    values = []
    
    for key, value in data.items():
        if key not in ['id', 'created_at', 'invoice_number']:
            fields.append(f"{key} = %s")
            if key == 'products':
                values.append(json.dumps(value, ensure_ascii=False))
            else:
                values.append(value)
    
    if not fields:
        return False
    
    values.append(order_id)
    query = f"UPDATE orders SET {', '.join(fields)} WHERE id = %s"
    
    cursor.execute(query, values)
    conn.commit()
    conn.close()
    
    return True
