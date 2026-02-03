import urllib.request
import json
from urllib.error import HTTPError

class WoolworthsData:
    def __init__(self, stock_code):
        self.url = f"https://www.woolworths.co.nz/api/v1/products/{stock_code}"
        self.headers = {'User-Agent': 'Mozilla/5.0', 'X-Requested-With': 'XMLHttpRequest'}

    def get_data(self):
        req = urllib.request.Request(self.url, headers=self.headers)
        try:
            with urllib.request.urlopen(req) as response:
                raw = json.loads(response.read().decode())
                p = raw.get("price", {})
                s = raw.get("size", {})

                return {
                    "Standard Pricing": {
                        "Current Price": p.get("salePrice"),
                        "Original Price": p.get("originalPrice"),
                        "Is Special": p.get("isSpecial"),
                        "Discount Percentage": f"{p.get('savePercentage')}%"
                    },
                    "Unit Economics": {
                        "Price per Kg/Unit": s.get("cupPrice"),
                        "Measure": s.get("cupMeasure"),
                        "Estimated Tray Price": p.get("averagePricePerSingleUnit"),
                        "Avg Pack Weight": raw.get("averageWeightPerUnit")
                    },
                    "Promotional Details": {
                        "Total Savings": p.get("savePrice"),
                        "Promo Start": p.get("promotionStartDate"),
                        "Promo End": p.get("promotionEndDate")
                    },
                }
        except HTTPError as e:
            if e.code == 404:
                return None
            else:
                raise
            
