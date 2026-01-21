import httpx
from typing import Optional
from config import DADATA_API_KEY, DADATA_SECRET_KEY


async def get_company_by_inn(inn: str) -> Optional[dict]:
    """Получение данных компании по ИНН через DaData API"""
    
    print(f"=== DaData Search ===")
    print(f"INN: {inn}")
    print(f"API Key exists: {bool(DADATA_API_KEY)}")
    print(f"API Key first 10 chars: {DADATA_API_KEY[:10] if DADATA_API_KEY else 'EMPTY'}")
    
    if not DADATA_API_KEY:
        print("ERROR: DADATA_API_KEY is empty!")
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
                json={"query": inn},
                timeout=10.0
            )
            
            print(f"Response status: {response.status_code}")
            print(f"Response body: {response.text[:500]}")
            
            if response.status_code != 200:
                print(f"ERROR: Bad status {response.status_code}")
                return None
                
            data = response.json()
            
            if data.get("suggestions"):
                suggestion = data["suggestions"][0]
                company_data = suggestion.get("data", {})
                
                result = {
                    "name": suggestion.get("value", ""),
                    "inn": company_data.get("inn", ""),
                    "kpp": company_data.get("kpp", ""),
                    "address": company_data.get("address", {}).get("value", ""),
                    "ogrn": company_data.get("ogrn", ""),
                }
                print(f"Found company: {result}")
                return result
            
            print("No suggestions found")
            return None
            
        except Exception as e:
            print(f"DaData exception: {e}")
            import traceback
            print(traceback.format_exc())
            return None
