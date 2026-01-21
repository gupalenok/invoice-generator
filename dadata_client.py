import httpx
from typing import Optional
from config import DADATA_API_KEY, DADATA_SECRET_KEY


async def get_company_by_inn(inn: str) -> Optional[dict]:
    """Получение данных компании по ИНН через DaData API"""
    
    if not DADATA_API_KEY:
        return None
    
    url = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/party"
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Token {DADATA_API_KEY}",
    }
    
    if DADATA_SECRET_KEY:
        headers["X-Secret"] = DADATA_SECRET_KEY
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                url,
                headers=headers,
                json={"query": inn}
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("suggestions"):
                suggestion = data["suggestions"][0]
                company_data = suggestion.get("data", {})
                
                return {
                    "name": suggestion.get("value", ""),
                    "inn": company_data.get("inn", ""),
                    "kpp": company_data.get("kpp", ""),
                    "address": company_data.get("address", {}).get("value", ""),
                    "ogrn": company_data.get("ogrn", ""),
                }
            
            return None
            
        except Exception as e:
            print(f"DaData error: {e}")
            return None
