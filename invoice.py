from typing import Dict


class Invoice:
    def __init__(self, json: Dict[str, str]):
        self.id = json["id"]
        self.number = json["number"]
        self.invoice_date = json["invoice_date"]
        self.sale_date = json["sale_date"]
        self.net_price = json["net_price"] / 100
        self.tax_price = json["tax_price"] / 100
        self.gross_price = json["gross_price"] / 100
        self.client_id = json["client_id"]

    def __str__(self):
        return f"""
id: {self.id}
number: {self.number}
invoice_date: {self.invoice_date}
sale_date: {self.sale_date}
net_price: {self.net_price}
tax_price: {self.tax_price}
gross_price: {self.gross_price}
client_id: {self.client_id}
"""
