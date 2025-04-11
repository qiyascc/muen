================================================
FILE: README.md
================================================
# trendyol-api-python-sdk
Unofficial Trendyol API Python SDK

## Installation

```sh
pip3 install trendyol-api-python-sdk
```

## Usage
```sh
from trendyol_sdk.api import TrendyolApiClient
from trendyol_sdk.services import ProductIntegrationService
api = TrendyolApiClient(api_key="<TRENDYOL_API_KEY>", api_secret="<TRENDYOL_API_SECRET>", supplier_id="<TRENDYOL_SELLER_ID>")
service = ProductIntegrationService(api)
products = service.get_products()
```

## Services Completion Status
- [x] Product Integration (Urun Entegrasyonu)
- [ ] Order Integration (Siparis Entegrasyonu)
- [ ] Common Label Integration (Ortak Etiken Entegrasyonu)
- [ ] Returned Orders Integration (Iade Entegrasyonu)
- [ ] Accounting And Finance Integration (Muhasebe ve Finans Entegrasyonu)
- [ ] Question And Answer Integration (Soru Cevap Entegrasyonu)



================================================
FILE: LICENSE
================================================
MIT License

Copyright (c) 2021 altuntasmuhammet

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.



================================================
FILE: MANIFEST.in
================================================
include setup.py README.md MANIFEST.in LICENSE AUTHORS requirements.txt


================================================
FILE: requirements.txt
================================================
requests



================================================
FILE: setup.py
================================================
import os
from setuptools import setup

# Utility function to read the README file.
# Used for the long_description.  It's nice, because now 1) we have a top level
# README file and 2) it's easier to type in the README file than to put a raw
# string in below ...
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

requirements_filename = os.path.join(os.path.dirname(__file__), 'requirements.txt')
with open(requirements_filename) as f:
    PACKAGE_INSTALL_REQUIRES = [line[:-1] for line in f]

setup(
    name = "trendyol_api_python_sdk",
    version = "0.0.8",
    author = "Muhammed Ali Altuntas",
    author_email = "altuntasmuhammet96@gmail.com",
    description = ("Unofficial Trendyol API Python Client"),
    license = "MIT",
    url="https://github.com/altuntasmuhammet/trendyol-api-python-sdk",
    packages=['trendyol_sdk'],
    long_description=read('README.md'),
    long_description_content_type="text/markdown",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=PACKAGE_INSTALL_REQUIRES,
    python_requires=">=3.0",
)



================================================
FILE: tests/__init__.py
================================================



================================================
FILE: trendyol_sdk/__init__.py
================================================



================================================
FILE: trendyol_sdk/api.py
================================================
import requests
from trendyol_sdk.utils import json_encode
from trendyol_sdk.exceptions import TrendyolAPIError

class TrendyolApiClient:

    def __init__(self, api_key, api_secret, supplier_id, integrator_name="SelfIntegration", is_test=False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.supplier_id = supplier_id
        self.integrator_name = integrator_name
        self.is_test = is_test
        self._session = TrendyolSession(api_key, api_secret)
    
    def call(self, method, url, params=None, headers=None, files=None):
        if not params:
            params = {}
        if not headers:
            headers = {}
        if not files:
            files = {}
        
        # set headers
        user_agent = "{} - {}".format(self.supplier_id, self.integrator_name)
        headers.update({
            "User-Agent": user_agent,
            "Content-Type": "application/json;charset=utf-8",
        })
        # call request
        if method in ('GET', 'DELETE'):
            response = self._session.requests.request(
                method,
                url,
                params=params,
                headers=headers,
                files=files,
                timeout=self._session.timeout
            )

        else:
            # Encode params
            params = json_encode(params)
            response = self._session.requests.request(
                method,
                url,
                data=params,
                headers=headers,
                files=files,
                timeout=self._session.timeout
            )
        
        if response.ok:
            return response.json()
        else:
            raise TrendyolAPIError("Call not successfull", response)

class TrendyolSession:
    
    def __init__(self, api_key, api_secret, timeout=None, http_adapter=None):
        self.api_key = api_key,
        self.api_secret = api_secret
        self.timeout=timeout
        self.http_adapter = http_adapter
        self.requests = requests.Session()
        self.requests.auth = (api_key, api_secret)
        if http_adapter:
            self.requests.mount("https://", http_adapter)



================================================
FILE: trendyol_sdk/exceptions.py
================================================
class TrendyolError(Exception):
    """
    Base class for Trendyol Api Error
    """
    pass


class TrendyolAPIError(TrendyolError):
    
    def __init__(self, message, response):
        self._message = message
        self._response = response
        
        super(TrendyolAPIError, self).__init__(
            "\n\n" +
            "  Message: %s\n" % self._message +
            "\n" +
            "  Status Code:  %s\n" % self._response.status_code +
            "  Response:\n    %s" % self._response.text +
            "\n"
        )


================================================
FILE: trendyol_sdk/services.py
================================================
from urllib.parse import urljoin
from trendyol_sdk import api

class BaseService:

    def __init__(self, api: 'api.TrendyolApiClient'):
        self._api = api
        if self._api.is_test:
            self.base_url = "https://stageapi.trendyol.com/stagesapigw/"
        else:
            self.base_url = "https://api.trendyol.com/sapigw/"


class ProductIntegrationService(BaseService):

    def __init__(self, api: 'api.TrendyolApiClient'):
        super(ProductIntegrationService, self).__init__(api)

    def get_suppliers_addresses(self, supplier_id=None):
        if supplier_id:
            endpoint = "suppliers/{}/addresses".format(supplier_id)
        else:
            endpoint = "suppliers/{}/addresses".format(self._api.supplier_id)
        url = urljoin(self.base_url, endpoint)
        data = self._api.call("GET", url, params=None, headers=None, files=None)
        return data

    def get_shipment_providers(self):
        endpoint = "shipment-providers"
        url = urljoin(self.base_url, endpoint)
        data = self._api.call("GET", url, params=None, headers=None, files=None)
        return data

    def get_brands(self, page, size):
        endpoint = "brands"
        url = urljoin(self.base_url, endpoint)
        params = {
            "page": page,
            "size": size
        }
        data = self._api.call("GET", url, params=params, headers=None, files=None)
        return data

    def get_brands_by_name(self, name):
        endpoint = "brands/by-name"
        url = urljoin(self.base_url, endpoint)
        params = {
            "name": name
        }
        data = self._api.call("GET", url, params=params, headers=None, files=None)
        return data

    def get_categories(self):
        endpoint = "product-categories"
        url = urljoin(self.base_url, endpoint)
        data = self._api.call("GET", url, params=None, headers=None, files=None)
        return data

    def get_category_attributes(self, category_id):
        endpoint = "product-categories/{}/attributes".format(category_id)
        url = urljoin(self.base_url, endpoint)
        params = {
            "category_id": category_id
        }
        data = self._api.call("GET", url, params=params, headers=None, files=None)
        return data

    def get_products(self, filter_params=None, supplier_id=None):
        if supplier_id:
            endpoint = "suppliers/{}/products".format(supplier_id)
        else:
            endpoint = "suppliers/{}/products".format(self._api.supplier_id)
        if not filter_params:
            filter_params = {}
        params = {
            "approved": filter_params.get("approved", None),
            "barcode": filter_params.get("barcode", None),
            "startDate": filter_params.get("startDate", None),
            "endDate": filter_params.get("endDate", None),
            "page": filter_params.get("page", None),
            "dateQueryType": filter_params.get("dateQueryType", None),
            "size": filter_params.get("size", None)
        }
        url = urljoin(self.base_url, endpoint)
        data = self._api.call("GET", url, params=params, headers=None, files=None)
        return data

    def create_products(self, items, supplier_id=None):
        if supplier_id:
            endpoint = "suppliers/{}/products".format(supplier_id)
        else:
            endpoint = "suppliers/{}/products".format(self._api.supplier_id)
        url = urljoin(self.base_url, endpoint)
        params = {
            "items": items
        }
        data = self._api.call("POST", url, params=params, headers=None, files=None)
        return data

    def update_products(self, items, supplier_id=None):
        if supplier_id:
            endpoint = "suppliers/{}/products".format(supplier_id)
        else:
            endpoint = "suppliers/{}/products".format(self._api.supplier_id)
        url = urljoin(self.base_url, endpoint)
        params = {
            "items": items
        }
        data = self._api.call("PUT", url, params=params, headers=None, files=None)
        return data

    def get_batch_requests(self, batch_request_id, supplier_id=None):
        if supplier_id:
            endpoint = "suppliers/{supplier_id}/products/batch-requests/{batch_request_id}".format(
                supplier_id=supplier_id,
                batch_request_id=batch_request_id
            )
        else:
            endpoint = "suppliers/{supplier_id}/products/batch-requests/{batch_request_id}".format(
                supplier_id=self._api.supplier_id,
                batch_request_id=batch_request_id
            )
        url = urljoin(self.base_url, endpoint)
        data = self._api.call("GET", url, params=None, headers=None, files=None)
        return data

    def update_price_and_stock(self, items, supplier_id=None):
        if supplier_id:
            endpoint = "suppliers/{supplier_id}/products/price-and-inventory".format(
                supplier_id=supplier_id
            )
        else:
            endpoint = "suppliers/{supplier_id}/products/price-and-inventory".format(
                supplier_id=self._api.supplier_id
            )
        url = urljoin(self.base_url, endpoint)
        params = {
            "items": items
        }
        data = self._api.call("POST", url, params=params, headers=None, files=None)
        return data
        

class OrderIntegrationService(BaseService):

    def __init__(self, api):
        super(OrderIntegrationService, self).__init__(api)

    def get_shipment_packages(self, filter_params, supplier_id=None):
        if supplier_id:
            endpoint = "suppliers/{}/orders".format(supplier_id)
        else:
            endpoint = "suppliers/{}/orders".format(self._api.supplier_id)
        if not filter_params:
            filter_params = {}
        params = {
            "startDate": filter_params.get("startDate", None),
            "endDate": filter_params.get("endDate", None),
            "page": filter_params.get("page", None),
            "size": filter_params.get("size", None),
            "orderNumber": filter_params.get("orderNumber", None),
            "status": filter_params.get("status", None),
            "orderByField": filter_params.get("orderByField", None),
            "orderByDirection": filter_params.get("orderByDirection", None),
            "shipmentPackageIds": filter_params.get("shipmentPackageIds", None)
        }
        url = urljoin(self.base_url, endpoint)
        data = self._api.call("GET", url, params=params, headers=None, files=None)
        return data

    def get_awaiting_shipment_packages(self):
        pass

    def update_tracking_number(self, shipment_package_id, tracking_number, supplier_id=None):
        if supplier_id:
            endpoint = "suppliers/{supplier_id}/{shipment_package_id}/update-tracking-number".format(
                supplier_id=supplier_id,
                shipment_package_id=shipment_package_id
            )
        else:
            endpoint = "suppliers/{supplier_id}/{shipment_package_id}/update-tracking-number".format(
                supplier_id=self._api.supplier_id,
                shipment_package_id=shipment_package_id
            )
        url = urljoin(self.base_url, endpoint)
        params = {
            "trackingNumber": tracking_number
        }
        data = self._api.call("PUT", url, params=params, headers=None, files=None)
        return data

    def update_shipment_package(self, shipment_package_id, status, lines=None, params=None, supplier_id=None):
        if supplier_id:
            endpoint = "suppliers/{supplier_id}/shipment-packages/{shipment_package_id}".format(
                supplier_id=supplier_id,
                shipment_package_id=shipment_package_id
            )
        else:
            endpoint = "suppliers/{supplier_id}/shipment-packages/{shipment_package_id}".format(
                supplier_id=self._api.supplier_id,
                shipment_package_id=shipment_package_id
            )
        url = urljoin(self.base_url, endpoint)
        params = {
            "status": status
        }
        if lines:
            params["lines"] = lines
        if params:
            params["params"] = params
        data = self._api.call("PUT", url, params=params, headers=None, files=None)
        return data

    def update_package_as_unsupplied(self):
        pass

    def send_invoice_link(self):
        pass

    def split_multi_package_by_quantity(self):
        pass

    def split_shipment_package(self):
        pass

    def split_multi_shipment_package(self):
        pass

    def split_shipment_package_by_quantity(self):
        pass

    def update_box_info(self):
        pass

    def process_alternative_delivery(self):
        pass

    def change_cargo_provider(self):
        pass


class CommonLabelIntegrationService(BaseService):

    def __init__(self, api):
        super(CommonLabelIntegrationService, self).__init__(api)

    def create_common_label(self):
        pass

    def get_common_label(self):
        pass

    def get_common_label_v2(self):
        pass


class ReturnedOrdersIntegrationService(BaseService):

    def __init__(self, api):
        super(ReturnedOrdersIntegrationService, self).__init__(api)

    def get_shipment_packages(self):
        pass

    def create_claim(self):
        pass

    def approve_claim_line_items(self):
        pass

    def create_claim_issue(self):
        pass

    def get_claim_issue_reasons(self):
        pass

    def get_claim_audits(self):
        pass


class AccountingAndFinanceIntegrationService(BaseService):

    def __init__(self, api):
        super(AccountingAndFinanceIntegrationService, self).__init__(api)

    def filter_with_date_validation_constraint(self):
        pass

    def get_settlements(self):
        pass

    def get_other_financials(self):
        pass


class QuestionAndAnswerIntegrationService(BaseService):

    def __init__(self, api):
        super(QuestionAndAnswerIntegrationService, self).__init__(api)

    def get_question_filters(self):
        pass

    def get_question_filter_by_id(self):
        pass

    def create_answer(self):
        pass



================================================
FILE: trendyol_sdk/utils.py
================================================
from json import dumps

def json_encode(data, ensure_ascii=False, encoding="utf-8"):
    return dumps(data, ensure_ascii=ensure_ascii).encode('utf-8')


================================================
FILE: .github/workflows/python-publish.yml
================================================
# This workflow will upload a Python Package using Twine when a release is created
# For more information see: https://help.github.com/en/actions/language-and-framework-guides/using-python-with-github-actions#publishing-to-package-registries

# This workflow uses actions that are not certified by GitHub.
# They are provided by a third-party and are governed by
# separate terms of service, privacy policy, and support
# documentation.

name: Upload Python Package

on:
  push:
    branches:
      - master

jobs:
  deploy:
    environment:
      name: production
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.x'
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install build
    - name: Build package
      run: python -m build
    - name: Publish package
      uses: pypa/gh-action-pypi-publish@27b31702a0e7fc50959f5ad993c78deac1bdfc29
      with:
        user: __token__
        password: ${{ secrets.PYPI_API_TOKEN }}


