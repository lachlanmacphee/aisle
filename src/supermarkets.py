import requests
import constants as c
from abc import ABC, abstractmethod
import os
import asyncio
from playwright.async_api import async_playwright


class Supermarket(ABC):
    @abstractmethod
    def __init__(self):
        pass

    @abstractmethod
    def search_products(self, search_term):
        pass

    @abstractmethod
    def place_order(self, order):
        pass


class Woolworths(Supermarket):
    auth: dict
    session: requests.Session
    database: object

    def __init__(self, database=None):
        email = os.getenv("WOOLWORTHS_EMAIL")
        password = os.getenv("WOOLWORTHS_PASSWORD")
        cvv = os.getenv("WOOLWORTHS_CARD_CVV")

        if not email or not password:
            raise ValueError(
                "WOOLWORTHS_EMAIL and WOOLWORTHS_PASSWORD environment variables must be set"
            )

        if not cvv:
            raise ValueError("WOOLWORTHS_CARD_CVV environment variable must be set")

        self.auth = {"email": email, "password": password, "cvv": cvv}
        self.database = database
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": c.USER_AGENT})
        self.session.get("https://www.woolworths.com.au/", timeout=10)

    def search_products(self, search_term):
        try:
            url = "https://www.woolworths.com.au/apis/ui/Search/products"

            request_body = {
                "Filters": [],
                "PageNumber": 1,
                "PageSize": 24,
                "SearchTerm": search_term,
                "SortType": "TraderRelevance",
                "ExcludeSearchTypes": ["UntraceableVendors"],
            }

            headers = {
                "Content-Type": "application/json",
                "Accept": "*/*",
            }

            response = self.session.post(
                url, json=request_body, headers=headers, timeout=10
            )

            if response.status_code == 200:
                search_results = response.json()
                if (
                    not search_results
                    or "Products" not in search_results
                    or not search_results["Products"]
                ):
                    return []

                products = []
                for product in search_results["Products"]:
                    # Check if the product has nested Products and it's not empty
                    if not product.get("Products") or len(product["Products"]) == 0:
                        continue

                    # Grab the most up-to-date product in the nested structure
                    nested_product = product["Products"][-1]
                    products.append(
                        {
                            "name": nested_product["DisplayName"],
                            "stockcode": str(nested_product["Stockcode"]),
                            "priceTotal": nested_product.get("Price", {}),
                            "priceUnitMeasure": nested_product.get("CupString", ""),
                            "isAvailable": nested_product.get("IsAvailable", False),
                            "isPurchasable": nested_product.get("IsPurchasable", False),
                        }
                    )

                available_purchasable_products = [
                    p for p in products if p["isAvailable"] and p["isPurchasable"]
                ]

                return available_purchasable_products
            else:
                return None

        except Exception:
            return None

    def place_order(self, order):
        asyncio.run(self._place_order_async(order))

    async def _place_order_async(self, order):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()

            try:
                await page.goto("https://auth.woolworths.com.au/u/login")
                await page.wait_for_load_state("networkidle")

                await page.fill('input[name="username"]', self.auth["email"])
                await page.fill('input[name="password"]', self.auth["password"])
                await page.click('button[type="submit"]')
                await page.wait_for_load_state("networkidle")

                await page.click('button:has-text("Continue")')
                await page.wait_for_selector('input[type="text"]', timeout=5000)

                await page.wait_for_timeout(10000)
                twofa_code = None
                if self.database:
                    twofa_code = self.database.get_latest_2fa_code()

                if not twofa_code:
                    twofa_code = input(
                        "Couldn't find 2FA code. Please type it manually and press Enter: "
                    )

                await page.fill('input[type="text"]', twofa_code)
                await page.click('button[type="submit"]')
                await page.wait_for_timeout(10000)

                for _, product in order.items():
                    stockcode = product["stockcode"]
                    product_name = product["name"]

                    product_url = (
                        f"https://www.woolworths.com.au/shop/productdetails/{stockcode}"
                    )
                    await page.goto(product_url)
                    await page.wait_for_load_state("networkidle")

                    selector = 'button[class="add-to-cart-btn"]'
                    is_out_of_stock = await page.locator(selector).first.is_disabled()
                    if is_out_of_stock:
                        print(f"Product {product_name} is out of stock")
                        continue
                    else:
                        print(f"Adding {product_name} to cart")
                        await page.locator(selector).first.click()

                # Click the cart button to open the drawer
                selector = "#header-view-cart-button"
                if await page.locator(selector).is_visible():
                    await page.click(selector)
                    await page.wait_for_load_state("networkidle")

                # Click the checkout button
                selector = 'button[type="submit"]'
                if await page.locator(selector).is_visible():
                    await page.click(selector)
                    await page.wait_for_load_state("networkidle")

                # The checkout button may lead to the delivery time selection,
                # or the "Have you forgotten?" page
                await page.wait_for_timeout(5000)
                forgotten_page = await page.get_by_text(
                    "Have You Forgotten?"
                ).is_visible()

                if forgotten_page:
                    await page.click(".continue-button")
                else:
                    time_slots = await page.query_selector_all(".time-slot")
                    if time_slots:
                        await time_slots[0].click()
                        await page.wait_for_timeout(5000)
                        await page.click('button[type="submit"]')
                    else:
                        raise Exception("No delivery time slots available")

                await page.wait_for_timeout(5000)

                # Sometimes we might get the forgotten page again
                # (or for the first time if the drawer was shown previously)
                forgotten_page = await page.get_by_text(
                    "Have You Forgotten?"
                ).is_visible()
                if forgotten_page:
                    await page.click(".continue-button")
                    await page.wait_for_timeout(5000)

                await page.fill('input[name="txt-cvv_csv"]', self.auth["cvv"])
                await page.click('button[type="submit"]')

                return True

            except Exception as e:
                print(f"Error during order placement: {str(e)}")
                return False

            finally:
                await browser.close()
