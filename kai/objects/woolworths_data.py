"""Fetches product pricing and unit data from the Woolworths NZ API."""
import requests

_REQUEST_TIMEOUT = 10


class WoolworthsData:
    def __init__(self, stock_code: str):
        self.url = f"https://www.woolworths.co.nz/api/v1/products/{stock_code}"
        self.headers = {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"}

    def get_data(self) -> dict:
        """Fetch product data for the stock code. Raises RuntimeError on failure."""
        try:
            response = requests.get(self.url, headers=self.headers, timeout=_REQUEST_TIMEOUT)
            response.raise_for_status()
            raw = response.json()
        except requests.RequestException as e:
            raise RuntimeError(f"Failed to fetch Woolworths data for {self.url}: {e}") from e

        p = raw.get("price", {})
        s = raw.get("size", {})

        # stock availability — try several field names the API uses
        stock_level = raw.get("stockLevel")
        is_available = raw.get("isAvailable")
        can_add = raw.get("canAddToCart")
        out_of_stock = (
            stock_level == 0
            or is_available is False
            or can_add is False
        )

        return {
            "Standard Pricing": {
                "Current Price": p.get("salePrice"),
                "Original Price": p.get("originalPrice"),
                "Is Special": p.get("isSpecial"),
                "Discount Percentage": f"{p.get('savePercentage')}%",
            },
            "Unit Economics": {
                "Price per Kg/Unit": s.get("cupPrice"),
                "Measure": s.get("cupMeasure"),
                "Estimated Tray Price": p.get("averagePricePerSingleUnit"),
                "Avg Pack Weight": raw.get("averageWeightPerUnit"),
            },
            "Promotional Details": {
                "Total Savings": p.get("savePrice"),
                "Promo Start": p.get("promotionStartDate"),
                "Promo End": p.get("promotionEndDate"),
            },
            "Availability": {
                "Out of Stock": out_of_stock,
                "Stock Level": stock_level,
            },
        }
