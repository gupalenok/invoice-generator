import sqlite3
from datetime import datetime
from typing import Optional
import json

DATABASE_NAME = "invoices.db"


def get_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'new',
            
            -- Товары (JSON массив)
            products TEXT,
            total_amount REAL,
            
            -- Данные заказчика из Тильды
            customer_name TEXT,
            customer_email TEXT,
            customer_phone TEXT,
            
            -- Данные организации (дозаполняются)
            company_name TEXT,
            company_inn TEXT,
            company_kpp TEXT,
            company_address TEXT,
            
            -- PDF
            pdf_generated INTEGER DEFAULT 0,
            
            -- CRM
            sent_to_crm INTEGER DEFAULT 0
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    # Инициализация счётчика
    cursor.execute(
        "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
        ("last_invoice_number", "0")
    )
    
    conn.commit()
    conn.close()


def get_next_invoice_number(prefix: str, start_number: int) -> str:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT value FROM settings WHERE key = 'last_invoice_number'")
    row = cursor.fetchone()
    last_number = int(row["value"]) if row else 0
    
    if last_number < start_number:
        last_number = start_number - 1
    
    new_number = last_number + 1
    
    cursor.execute(
        "UPDATE settings SET value = ? WHERE key = 'last_invoice_number'",
        (str(new_number),)
    )
    conn.commit()
    conn.close()
    
    return f"{prefix}-{new_number:08d}"


def create_order(
    products: list,
    total_amount: float,
    customer_name: str,
    customer_email: str,
    customer_phone: str,
    invoice_prefix: str,
    start_number: int
) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    
    invoice_number = get_next_invoice_number(invoice_prefix, start_number)
    
    cursor.execute("""
        INSERT INTO orders (
            invoice_number, products, total_amount,
            customer_name, customer_email, customer_phone
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, (
        invoice_number,
        json.dumps(products, ensure_ascii=False),
        total_amount,
        customer_name,
        customer_email,
        customer_phone
    ))
    
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return order_id


def get_order(order_id: int) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        order = dict(row)
        order["products"] = json.loads(order["products"]) if order["products"] else []
        return order
    return None


def get_all_orders() -> list:
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


def update_order_company(
    order_id: int,
    company_name: str,
    company_inn: str,
    company_kpp: str,
    company_address: str
):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE orders SET
            company_name = ?,
            company_inn = ?,
            company_kpp = ?,
            company_address = ?,
            status = 'filled'
        WHERE id = ?
    """, (company_name, company_inn, company_kpp, company_address, order_id))
    
    conn.commit()
    conn.close()


def mark_pdf_generated(order_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE orders SET pdf_generated = 1, status = 'invoice_created'
        WHERE id = ?
    """, (order_id,))
    
    conn.commit()
    conn.close()


def mark_sent_to_crm(order_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE orders SET sent_to_crm = 1, status = 'sent_to_crm'
        WHERE id = ?
    """, (order_id,))
    
    conn.commit()
    conn.close()
