import threading
import supermarkets as sm
import database as db
import constants as c
from dotenv import load_dotenv
from ollama import chat
from ollama import ChatResponse
from flask import Flask, request, jsonify


def Aisle():
    load_dotenv()
    app = Flask(__name__)
    database = db.Database()
    supermarket = sm.Woolworths(database)

    def shopping_list_to_order(shopping_list):
        order = {}

        for item in shopping_list:
            products = supermarket.search_products(item)

            if not products or len(products) == 0:
                print(f"No products found for '{item}'")
                continue

            found_exact_match = False
            for product in products:
                if product["name"].lower() == item.lower():
                    order[item] = product
                    found_exact_match = True
                    break

            if found_exact_match:
                continue

            # If no exact match, try to find whether one of the products has been ordered before
            found_past_order = False
            for product in products:
                last_stockcode = database.find_stockcode_in_past_orders(
                    product["stockcode"]
                )
                if last_stockcode:
                    order[item] = product
                    found_past_order = True
                    break

            if found_past_order:
                continue

            products_for_llm = ", ".join(
                [f"{p['stockcode']}: {p['name']}" for p in products]
            )

            additional_instructions = (
                "Avoid plant-based products if a meat-option is available."
            )

            # If still no match, use an LLM to select the best product based on its knowledge
            response: ChatResponse = chat(
                model="gemma3n",
                messages=[
                    {
                        "role": "user",
                        "content": f"Given the following products:\n\n{products_for_llm}\n\nAnd the shopping list item '{item}'\n\nWhich product would you recommend based on your own knowledge? Please return only the product's integer code in your response. In other words, your response should only contain an integer matching one of the codes. Your response must contain a code. Do not return anything else. {additional_instructions}",
                    },
                ],
            )

            found_ai_match = False
            if response.message.content:
                stockcode = response.message.content
                for product in products:
                    if product["stockcode"] == stockcode:
                        order[item] = product
                        found_ai_match = True
                        break

            if found_ai_match:
                continue

            # If no match found, use the first product as a fallback
            order[item] = products[0]

        return order

    @app.route("/submit-2fa", methods=["POST"])
    def submit_2fa():
        try:
            data = request.get_json()
            message = data.get("message", "")

            if not message:
                return jsonify({"error": "Message is required"}), 400

            message_id = database.store_sms_message(message)

            return (
                jsonify(
                    {
                        "success": True,
                        "message_id": message_id,
                        "message": "2FA message stored successfully",
                    }
                ),
                200,
            )

        except Exception as e:
            return jsonify({"error": "Internal server error", "details": str(e)}), 500

    @app.route("/order", methods=["POST"])
    def order():
        try:
            data = request.get_json()
            shopping_list = data.get("shopping_list", [])

            if not shopping_list:
                return jsonify({"error": "Shopping list is required"}), 400

            def process_order():
                try:
                    order = shopping_list_to_order(shopping_list)
                    success = supermarket.place_order(order)

                    if success:
                        database.store_order(order)
                        print("Order processed and stored successfully!")
                    else:
                        print("Order placement failed")

                except Exception as e:
                    print(f"Error processing order: {str(e)}")

            order_thread = threading.Thread(target=process_order, daemon=True)
            order_thread.start()

            return (
                jsonify(
                    {
                        "success": True,
                        "message": "Order processing started",
                        "items": shopping_list,
                    }
                ),
                202,
            )

        except Exception as e:
            return jsonify({"error": "Internal server error", "details": str(e)}), 500

    return app


if __name__ == "__main__":
    app = Aisle()
    app.run(debug=True, host=c.HOST, port=c.PORT)
