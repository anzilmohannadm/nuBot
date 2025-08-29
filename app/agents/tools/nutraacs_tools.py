import httpx
import json
import logging
import traceback
from langchain_core.tools import tool
from typing import TypedDict,Optional,List,Dict,Any
from langchain_core.runnables import RunnableConfig
from app.agents.utils.general_methods import get_media_id,send_whatsapp_document
from app.utils.secureconfig import ConfigParserCrypt
from app.utils.conf_path import str_configpath
from app.utils.global_config import env_mode

# Configure logging to print only to console
logging.basicConfig(level=logging.INFO)


ins_cfg = ConfigParserCrypt()
ins_cfg.read(str_configpath)
NUTRAACS_URL = ins_cfg.get(env_mode, 'NUTRAACS_URL')

class Customer(TypedDict):
    intPk: int
    strCode: str
    strDefaultCurrency: str
    strName: str
    strNameCode: str
    strEmail: str
    strPhone: str
    strAddress: str
    strMobile: str
    strVatNo: str
    strContactPerson: str
    blnPrintWithAttachment: bool
    intStatePk: Optional[int]
    blnApplyTcs: bool
    arrTaxExemptedServices: List
    arrStockTaxExemptedServices: List
    blnActAsCustomer: bool
    intCustomerRoll: int
    objSalesMan: Optional[Dict[str, Any]] = None
    intPrivilegedAccId: Optional[int]
    intUserId: Optional[int]
    objMainLedger: Optional[Dict[str, Any]] = None
    arrCurrency: List[str]
    strBrn: Optional[str]
    objCreditLimit:Optional[Dict[str, Any]] = None

@tool
async def get_customer_details(
    customer: str,
    config: RunnableConfig) -> List[Customer]:
    """
    Retrieve customer details by matching the user's input against the system's autocomplete API.

    This function uses the first character of the input string to query the autocomplete endpoint,
    fetches a list of matching customers, and returns the result.

    Args:
        customer (str): The customer name input provided by the user.
        config (RunnableConfig): Runtime configuration containing access token and other parameters.

    Returns:
        List[Customer]: A list of matching customer objects returned by the autocomplete API.
    """
    try:
      first_char = customer.strip()[0] if customer else ""
      header = {
          "Content-Type": "application/json",
          "Accept": "*/*",
          "Accept-Encoding": "gzip, deflate, br",
          "Origin":f"{NUTRAACS_URL}",
          "Referer":f"{NUTRAACS_URL}/rpt/customer_reports/soa",
          "X-Access-Token": f"Bearer {config.get('configurable', {}).get('token')}"
      }
      
      payload = {"strValue":f"{first_char}","objParameters":{"strType":"CUSTOMER_ACCOUNT","blnGetDefaultMainLedger":True,"intLimit":10,"blnShowInactive":True,"blnReport":True}}
      async with httpx.AsyncClient() as client:
        response = await client.post(f"{NUTRAACS_URL}/api/common/autocomplete/get_autocomplete", headers=header, data=json.dumps(payload))
        if response.status_code == 200:
            return response.json()
        else:
            raise ValueError(
                  f"Failed to fetch customer details: {response.status_code} - {response.text}"
              )
  
    except Exception:
      traceback.print_exc()

@tool
async def download_statement_of_accounts(
    from_date: str,
    to_date: str,
    customer: Customer,
    config: RunnableConfig
) -> List[Dict]:
    """
    Download a PDF of the account statement within the specified date range.

    Args:
        from_date (str): Start date in DD/MM/YYYY format.
        to_date (str): End date in DD/MM/YYYY format.
        customer (Customer): Full customer object. To obtain it, call get_customer_details with a user input and select the correct customer from the result.
        config (RunnableConfig): Configuration for the runtime.
    
    Returns:
        List[Dict]: Downloaded statement data.
    """
    header = {
        "Content-Type": "application/json",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Origin":f"{NUTRAACS_URL}",
        "Referer":f"{NUTRAACS_URL}/rpt/customer_reports/soa",
        "X-Access-Token": f"Bearer {config.get('configurable', {}).get('token')}"
    }
    payload = {
  "objPagination": {},
  "objSort": {},
  "objFilter": {
    "datFromDate": from_date,
    "datToDate": to_date,
    "objAccountId": {
      'intPk': customer['intPk'],
        'strCode':customer['strCode'],
        'strDefaultCurrency': customer['strDefaultCurrency'],
        'strName' : customer['strName'],
        'strNameCode' : customer['strNameCode'],
        'strEmail' : customer['strEmail'],
        'strPhone' : customer['strPhone'],
        "strAddress":customer['strAddress'],
        "strMobile": customer['strMobile'],
        "strVatNo": customer['strVatNo'],
        "strContactPerson": customer['strContactPerson'],
        "blnPrintWithAttachment": customer['blnPrintWithAttachment'],
        "intStatePk": customer['intStatePk'],
        "blnApplyTcs": customer['blnApplyTcs'],
        "arrTaxExemptedServices": [],
        "arrStockTaxExemptedServices": [],
        "blnActAsCustomer": customer['blnActAsCustomer'],
        "intCustomerRoll": customer['intCustomerRoll'],
        "objSalesMan": {
            "intPk": customer['objSalesMan'],
            "strEmployeeCode": None,
            "strEmployeeName": None,
            "strEmployeeCodeName": None,
            "strPhone": None,
            "strEmail": None
        },
        "intPrivilegedAccId": None,
        "intUserId": None,
        "objMainLedger": {
            "intPk": customer['intPk'],
            "strCode": customer['strCode'],
            "strName": customer['strName'],
            "strNameCode": customer['strNameCode']
        },
        "arrCurrency": [
            customer['arrCurrency']
        ],
        "strBrn": None,
        "objCreditLimit": {
            "strCreditLimit": "",
            "strDueDateRule": "NONE",
            "datDateWiseDate": "",
            "strExtraCreditLimit": "",
            "strCreditDays": 0,
            "strExtraCreditDays": "",
            "blnEmailForCreditLimit": False,
            "blnCreditLimitBlocking": False,
            "blnConsiderIssuerenceAmount": False,
            "blnEnableEmailAlert": False,
            "arrAlertAccounts": [],
            "intEmailTemplateForBlockingId": None,
            "intEmailTemplateForWarningId": None
      }
    },
    "objMainLedgerId": {
      "intPk": 39,
      "strCode": "1045101",
      "strName": "DEBTORS ACCOUNTS",
      "strNameCode": "1045101 : DEBTORS ACCOUNTS"
    },
    "arrCurrencyName": [
      "USD"
    ],
    "strRefference": "",
    "blnFullStatement": True,
    "blnOutStanding": False,
    "strBaseCurrency": "USD",
    "blnConsiderMatching": False,
    "strConsolidationCurrency": "USD",
    "blnAgeing": False,
    "strModule": "CUSTOMER_SOA",
    "blnShowOverdueDays": None,
    "blnShowMatchedDoc": "",
    "strDateType": "TRANSACTION_DATE",
    "blnGetAllData": True,
    "blnExcludeAgainstInvoice": False,
    "strOrientation": "LANDSCAPE",
    "strUserDefaultBranchCode": "MAIN"
  },
  "objColumns": {
    "arrColumns": [
      {
        "strHeader": "COMMON.DATE",
        "strKey": "datTransactionDate",
        "blnShow": True,
        "intColSpan": 1,
        "intRowSpan": 1,
        "blnAllowSorting": True,
        "blnAllowOrdering": False,
        "blnAllowHide": True,
        "strWidth": "100px"
      },
      {
        "strHeader": "LABELS.DOCNO",
        "strKey": "strDocumentNo",
        "blnShow": True,
        "intColSpan": 1,
        "intRowSpan": 1,
        "blnAllowSorting": True,
        "blnAllowOrdering": False,
        "blnAllowHide": True,
        "strWidth": "140px"
      },
      {
        "strHeader": "LABELS.DEBIT",
        "strKey": "strReceivedAmount",
        "blnShow": True,
        "intColSpan": 1,
        "intRowSpan": 1,
        "blnAllowSorting": False,
        "blnAllowOrdering": True,
        "strAlign": "RIGHT",
        "blnAllowHide": True,
        "strWidth": "150px"
      },
      {
        "strHeader": "LABELS.CREDIT",
        "strKey": "strPaidAmount",
        "blnShow": True,
        "intColSpan": 1,
        "intRowSpan": 1,
        "blnAllowSorting": False,
        "blnAllowOrdering": True,
        "strAlign": "RIGHT",
        "blnAllowHide": True,
        "strWidth": "150px"
      },
      {
        "strHeader": "LABELS.ROE",
        "strKey": "dblRoe",
        "blnShow": False,
        "intColSpan": 1,
        "intRowSpan": 1,
        "blnAllowSorting": False,
        "blnAllowOrdering": True,
        "strAlign": "RIGHT",
        "blnAllowHide": True,
        "strWidth": "150px"
      },
      {
        "strHeader": "LABELS.BALANCE",
        "strKey": "strBalanceAmount",
        "blnShow": True,
        "intColSpan": 1,
        "intRowSpan": 1,
        "blnAllowSorting": False,
        "blnAllowOrdering": True,
        "strAlign": "RIGHT",
        "blnAllowHide": True,
        "strWidth": "150px"
      },
      {
        "strHeader": "LABELS.LPO_NO",
        "strKey": "strLpoNo",
        "blnShow": True,
        "intColSpan": 1,
        "intRowSpan": 1,
        "blnAllowSorting": False,
        "blnAllowOrdering": True,
        "blnAllowHide": True,
        "strWidth": "130px"
      },
      {
        "strHeader": "LABELS.NARRATION",
        "strKey": "strNarration",
        "blnShow": True,
        "intColSpan": 1,
        "intRowSpan": 1,
        "blnAllowSorting": False,
        "blnAllowOrdering": True,
        "blnAllowHide": True,
        "strWidth": "300px"
      },
      {
        "strHeader": "LABELS.MATCHED_DOCS",
        "strKey": "strMatchedDocument",
        "blnShow": False,
        "intColSpan": 1,
        "intRowSpan": 1,
        "blnAllowSorting": False,
        "blnAllowOrdering": True,
        "blnAllowHide": False,
        "strWidth": "200px"
      },
      {
        "strHeader": "LABELS.OVERDUE_DAYS",
        "strKey": "stOverDueDays",
        "blnShow": False,
        "intColSpan": 1,
        "intRowSpan": 1,
        "blnAllowSorting": False,
        "blnAllowOrdering": True,
        "blnAllowHide": False,
        "strWidth": "170px"
      },
      {
        "strHeader": "LABELS.REFERENCE",
        "strKey": "strReference",
        "blnShow": False,
        "intColSpan": 1,
        "intRowSpan": 1,
        "blnAllowSorting": False,
        "blnAllowOrdering": True,
        "blnAllowHide": True,
        "blnAllowPrintHide": True,
        "blnPrintShow": False,
        "strWidth": "300px"
      },
      {
        "strHeader": "LABELS.CREDIT_DUE_DATE",
        "strKey": "strDueDate",
        "blnShow": True,
        "intColSpan": 1,
        "intRowSpan": 1,
        "blnAllowSorting": False,
        "blnAllowOrdering": True,
        "blnAllowHide": True,
        "strWidth": "170px"
      }
    ]
  },
  "objAgeingColumns": {
    "arrColumns": [
      {
        "strHeader": "LABELS.PERIOD",
        "strKey": "strPeriod",
        "blnShow": True,
        "intColSpan": 1,
        "intRowSpan": 1,
        "blnAllowSorting": False,
        "blnAllowOrdering": False,
        "blnAllowHide": True,
        "strWidth": "150px"
      },
      {
        "strHeader": "LABELS.DEBIT",
        "strKey": "strDebitAmount",
        "blnShow": True,
        "intColSpan": 1,
        "intRowSpan": 1,
        "blnAllowSorting": False,
        "blnAllowOrdering": False,
        "strAlign": "RIGHT",
        "blnAllowHide": True,
        "strWidth": "150px"
      },
      {
        "strHeader": "LABELS.CREDIT",
        "strKey": "strCreditAmount",
        "blnShow": True,
        "intColSpan": 1,
        "intRowSpan": 1,
        "blnAllowSorting": False,
        "blnAllowOrdering": False,
        "strAlign": "RIGHT",
        "blnAllowHide": True,
        "strWidth": "150px"
      },
      {
        "strHeader": "LABELS.NET_BALANCE",
        "strKey": "strNetBalance",
        "blnShow": True,
        "intColSpan": 1,
        "intRowSpan": 1,
        "blnAllowSorting": False,
        "blnAllowOrdering": False,
        "strAlign": "RIGHT",
        "blnAllowHide": True,
        "strWidth": "150px"
      }
    ]
  },
  "strType": ".pdf",
  "strTaxLabel": "VAT"
}
    
    # Make the API request
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{NUTRAACS_URL}/api/print/print/get_customer_soa_export", headers=header, data=json.dumps(payload))
            # Check if the request was successful
            if response.status_code == 200:
                file_data = response.content
                file_name = "Statement of account"
                caption = f"Account statement of {customer['strName']} from {from_date} to {to_date}"
                whatsapp_body = config.get('configurable', {}).get('whatsapp_body')
                whatsapp_token = config.get('configurable', {}).get('whatsapp_token')
                media_id = await get_media_id(whatsapp_body,file_data,whatsapp_token)
                response = await send_whatsapp_document(whatsapp_body,media_id,whatsapp_token,file_name,caption)
                return "Your account statement has been generated successfully!"
        
    except Exception as ex:
        print(str(ex))
    else:
        # Handle errors
        raise Exception(f"Error fetching data: {response.status_code}")


__all__ = ["download_statement_of_accounts","get_customer_details"]