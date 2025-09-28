# aisle - Automated Grocery Ordering

aisle provides an HTTP server for ordering groceries from your supermarket, with HTTP endpoints for 2FA handling and shopping list submission. Currently, only Woolworths in Australia is supported, but the architecture allows for easy addition of other supermarkets if you wish to contribute another.

## Features

- **Shopping List Orders**: Submit shopping lists via the HTTP API for automated ordering
- **Database Storage**: SQLite database for previous orders and their items for improved product matching
- **AI-Powered Product Matching**: Uses Ollama for intelligent product selection when exact matches are not found
- **2FA Handling**: Stores and automatically uses 2FA codes received via SMS from your iPhone

## Roadmap

- [ ] Still seems to add products to cart that are out of stock (search api may not have stock info, might have to loop them through again?)
- [ ] Shipping preferences in checkout
- [ ] Home Assistant integration to source the shopping list, trigger orders, and check delivery status
- [ ] Switch away from Ollama to a hosted LLM solution (e.g. OpenRouter, LiteLLM proxy)

## Setup

1. Install dependencies:

```bash
pip3 install -r requirements.txt
```

2. Copy the example environment variables file to your own `.env` file:

```bash
cp .env.example .env
```

2. Modify the `.env` file with your Woolworths credentials:

```
WOOLWORTHS_EMAIL=your_email@example.com
WOOLWORTHS_PASSWORD=your_password
WOOLWORTHS_CARD_CVV=123
```

3. Install Playwright browsers:

```bash
python3 -m playwright install
```

## Usage

### Running the HTTP Server

Start the server:

```bash
python3 src/main.py
```

The server will be available at `http://localhost` and `http://your-computer-ip-on-local-network`

### Available Endpoints

#### 1. Place Orders

**POST** `/order`

Submit a shopping list for automated ordering.

**JSON Request:**

```json
{
  "shopping_list": ["white bread", "milk 1l", "eggs", "bananas"]
}
```

#### 2. Submit 2FA Messages

**POST** `/submit-2fa`

Submit 2FA SMS messages that will be stored and automatically used during login. You can automate these submissions using the Shortcuts app on your iPhone.

**JSON Request:**

```json
{
  "message": "Your Woolworths verification code is 123456. Valid for 5 minutes."
}
```

### Database Tables

The system creates the following SQLite tables:

- `orders`: Stores order information
- `order_items`: Stores individual items for each order
- `sms_messages`: Stores SMS messages and tracks usage

## How It Works

Once you've submitted a shopping list via the `/order` endpoint:

1. **Login**: Using your credentials, the browser (running in the background) will log into Woolworths. If 2FA is required, it waits for a valid 2FA code to be submitted via the `/submit-2fa` endpoint.

2. **Product Matching**: aisle uses multiple strategies in the following order to match shopping list items to products:

   - Exact name matching
   - Previous order history
   - AI-powered product selection using Ollama

3. **Checkout**: The matched products are added to the cart, and the browser navigates to the checkout page where it will choose the soonest available delivery slot.
