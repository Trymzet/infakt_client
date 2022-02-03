import toml
import requests
from typing import Dict, Any
import datetime
from invoice import Invoice
from loguru import logger
from pydantic import BaseModel, validator
import calendar
from functools import reduce


class Config(BaseModel):
    title: str
    credentials: Dict[str, str]
    defaults: Dict[str, Any]

    @validator("credentials", pre=True)
    def validate_creds(cls, creds):
        api_key = creds.get("api_key", "")
        assert len(api_key) == 40, "Please provide a valid API key."
        return creds


class Client:
    API_URL = "https://api.infakt.pl:443/api/v3/"

    def __init__(self, config_path: str = "config.toml"):
        self.logger = logger
        self.logger.bind(client=True)
        self.config_path = config_path

    def _get_config(self) -> Config:
        return Config(**toml.load(self.config_path))

    def _get_headers(self):
        return {"X-inFakt-ApiKey": self._get_config().credentials["api_key"]}

    def get_invoice(self, invoice_number: int) -> Invoice:

        self.logger.info(f"Retrieving invoice no. {invoice_number}...")

        endpoint = self.API_URL + "invoices/"
        response = requests.get(
            endpoint + str(invoice_number) + ".json",
            headers=self._get_headers(),
        )
        invoice = Invoice(response.json())

        self.logger.info(f"Successfully retrieved invoice no. {invoice_number}.")
        self.logger.info(invoice)
        return invoice

    # def _generate_pdf(self, invoiceNum):
    #     response = requests.get(
    #         self.API_URL
    #         + "/invoices/"
    #         + str(invoiceNum)
    #         + "/pdf.json?document_type=original&locale=pe",
    #         headers=self._prepareHeaders(),
    #     )
    #     fileName = str(invoiceNum) + ".pdf"
    #     with open(fileName, "wb") as fd:
    #         for chunk in response.iter_content(chunk_size=128):
    #             fd.write(chunk)
    #         fd.close()
    #     log.info("Saved invoice as {}".format(fileName))

    def send_invoice(
        self, invoice_number: int, email: str, send_copy: bool = True
    ) -> bool:

        email = (
            email
            if email is not None
            else self._get_default_from_config("invoice.client_email")
        )

        endpoint = self.API_URL + "invoices/"

        data = {
            "print_type": "original",
            "locale": "pe",
            "recipient": email,
            "send_copy": send_copy,
        }
        response = requests.post(
            endpoint + str(invoice_number) + "/deliver_via_email.json",
            headers=self._get_headers(),
            data=data,
        )

        if not response.ok:
            return False

        return True

    def _get_default_invoice_date(self) -> str:
        today = datetime.date.today()
        first = today.replace(day=1)

        # January special case
        if today.month == 1:
            if today.day < 15:
                year = today.year - 1
                month = 12
            else:
                year = today.year
                month = today.month
        else:
            year = today.year
            if today.day < 15:
                # Assume we're billing for previous month
                month = (first - datetime.timedelta(days=1)).month
            else:
                month = today.month
        day = calendar.monthrange(year, month)[1]

        # Ensure MM and DD format
        month = str(month).zfill(2)
        day = str(day).zfill(2)

        return f"{year}-{month}-{day}"

    def _get_payment_date(self, invoice_date: str, payment_days: int) -> str:
        date_obj = datetime.datetime.strptime(invoice_date, "%Y-%m-%d").date()
        payment_date_obj = date_obj + datetime.timedelta(days=payment_days)
        year = payment_date_obj.year
        month = payment_date_obj.month
        day = payment_date_obj.day

        # Ensure MM and DD format
        month = str(month).zfill(2)
        day = str(day).zfill(2)

        return f"{year}-{month}-{day}"

    def _get_default_from_config(self, value):
        def deep_get(dictionary, keys, default=None):
            return reduce(
                lambda d, key: d.get(key, default) if isinstance(d, dict) else default,
                keys.split("."),
                dictionary,
            )

        config_dict = self._get_config().dict()
        return deep_get(config_dict, "defaults" + "." + value)

    def create_invoice(
        self,
        gross_price: float,  # in grosz
        service_name: str = None,
        client_id: int = None,
        sale_date: str = None,
        invoice_date: str = None,
        payment_date: str = None,
        payment_days: int = 14,
        gtu_id: int = None,
    ) -> Invoice:
        service_name = (
            service_name
            if service_name is not None
            else self._get_default_from_config("invoice.service.name")
        )
        client_id = (
            client_id
            if client_id is not None
            else self._get_default_from_config("invoice.client_id")
        )
        gtu_id = (
            gtu_id
            if gtu_id is not None
            else self._get_default_from_config("invoice.service.gtu_id")
        )
        default_invoice_date = self._get_default_invoice_date()
        default_payment_date = self._get_payment_date(
            default_invoice_date, payment_days
        )
        sale_date = sale_date if sale_date is not None else default_invoice_date
        invoice_date = (
            invoice_date if invoice_date is not None else default_invoice_date
        )
        payment_date = (
            payment_date if payment_date is not None else default_payment_date
        )
        payload = {
            "invoice": {
                "client_id": str(client_id),
                "payment_method": "transfer",
                "sale_date": sale_date,
                "invoice_date": invoice_date,
                "payment_date": payment_date,
                "services": [
                    {
                        "name": service_name,
                        "gross_price": gross_price * 100,
                        "tax_symbol": 23,
                        "gtu_id": gtu_id,
                    }
                ],
            }
        }
        response = requests.post(
            self.API_URL + "invoices.json",
            headers=self._get_headers(),
            json=payload,
        )
        response.raise_for_status()
        invoice = Invoice(response.json())
        return invoice

    def delete_invoice(self, invoice_number: int) -> bool:
        endpoint = self.API_URL + "invoices/"
        response = requests.delete(
            endpoint + str(invoice_number) + ".json",
            headers=self._get_headers(),
        )
        return response.ok

    def create_and_send_invoice(
        self, gross_price: float, email: str = None, send_copy: bool = True, **kwargs
    ) -> bool:
        invoice = self.create_invoice(gross_price, **kwargs)
        was_sent = self.send_invoice(invoice.id, email=email, send_copy=send_copy)
        return was_sent


amount = 28615

c = Client()
c.create_and_send_invoice(amount)
