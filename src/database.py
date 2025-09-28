import sqlite3
import constants as c


class Database:
    con: sqlite3.Connection
    cur: sqlite3.Cursor

    def __init__(self):
        self.con = sqlite3.connect(c.DB_NAME, check_same_thread=False)
        self.cur = self.con.cursor()
        self.migrate()

    def migrate(self):
        self.cur.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_date TEXT NOT NULL
            )
        """
        )

        self.cur.execute(
            """
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                stockcode TEXT NOT NULL,
                price_total REAL NOT NULL,
                price_unit_measure TEXT NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders (id)
            )
        """
        )

        self.cur.execute(
            """
            CREATE TABLE IF NOT EXISTS sms_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_body TEXT NOT NULL,
                received_at TEXT NOT NULL DEFAULT (datetime('now')),
                used BOOLEAN DEFAULT FALSE
            )
        """
        )

    def find_stockcode_in_past_orders(self, stockcode: str) -> bool:
        return self.cur.execute(
            "SELECT stockcode FROM order_items WHERE stockcode = ? ORDER BY id DESC LIMIT 1",
            (stockcode,),
        ).fetchone()

    def store_order(self, order):
        self.cur.execute("INSERT INTO orders (order_date) VALUES (datetime('now'))")
        self.con.commit()
        order_id = self.cur.lastrowid

        for _, product in order.items():
            self.cur.execute(
                "INSERT INTO order_items (order_id, product_name, stockcode, price_total, price_unit_measure) VALUES (?, ?, ?, ?, ?)",
                (
                    order_id,
                    product["name"],
                    product["stockcode"],
                    product["priceTotal"],
                    product["priceUnitMeasure"],
                ),
            )

        self.con.commit()
        return order_id

    def store_sms_message(self, message_body):
        self.cur.execute(
            "INSERT INTO sms_messages (message_body) VALUES (?)", (message_body,)
        )
        self.con.commit()
        return self.cur.lastrowid

    def get_latest_2fa_code(self):
        self.cur.execute(
            "SELECT id, message_body FROM sms_messages WHERE used = FALSE ORDER BY received_at DESC LIMIT 1"
        )
        result = self.cur.fetchone()

        if result:
            message_id, message_body = result
            import re

            code_match = re.search(r"\b\d{6}\b", message_body)
            if code_match:
                self.cur.execute(
                    "UPDATE sms_messages SET used = TRUE WHERE id = ?", (message_id,)
                )
                self.con.commit()
                return code_match.group()

        return None
