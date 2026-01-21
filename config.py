import os

# DaData API
DADATA_API_KEY = os.getenv("DADATA_API_KEY", "6331710129b8363a28b4e9697f9d8f6342a166a2")
DADATA_SECRET_KEY = os.getenv("DADATA_SECRET_KEY", "69cc9c50ba5a37a3ec0522bafcf53ff826ccb956")

# Реквизиты вашей компании (исполнитель)
COMPANY = {
    "name": "ООО «Чипмедиа.ру»",
    "name_full": "Общество с ограниченной ответственностью «Чипмедиа.ру»",
    "inn": "7203406721",
    "kpp": "720301001",
    "ogrn": "1167232094677",
    "address": "625003, г. Тюмень, ул. Володарского, дом 14, кб. 505",
    "phone": "8(3452) 612-950",
    "email": "info@cheapmedia.ru",
    "bank_name": "ЗАПАДНО-СИБИРСКОЕ ОТДЕЛЕНИЕ №8647 ПАО СБЕРБАНК",
    "bik": "047102651",
    "account": "40702810267100005911",
    "corr_account": "30101810800000000651",
}

# Настройки счёта
INVOICE_PREFIX = "ЧМ"
INVOICE_START_NUMBER = 1

# Срок оплаты (дней от даты счёта)
PAYMENT_DAYS = 3
