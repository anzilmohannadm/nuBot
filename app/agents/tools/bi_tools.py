import requests
import json
from langchain_core.tools import tool
from typing import cast, List, Dict, Optional
from typing_extensions import TypedDict
from langchain_core.runnables import RunnableConfig
import logging

# Configure logging to print only to console
logging.basicConfig(level=logging.INFO)


header = {
    "Content-Type": "application/json",
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br",
}


@tool
def fetch_master_info(config: RunnableConfig) -> List[Dict]:
    """
    Retrieves essential business details, including branch information, customer data, transaction status, and form of payment (FOP), along with their corresponding names and IDs.

    These basic details are required for further processing and can be utilized by other tools.

    Returns:
        List[dict]: A list of dictionaries containing the retrieved business details, including IDs and names.
    """
    # Example API endpoint
    results = []
    url = config.get("configurable", {}).get("domain")
    master_payload = {
        "from_date": "01-01-1900",
        "to_date": "01-01-2050",
        "category": ["branch", "customer", "status", "fop"],
        "module": "all",
        "dashboard": "branch",
        "filter": {},
        "sort_by": "current_period_sales",
    }

    # Make the API request
    response = requests.request(
        "GET",
        url + "/api/mobApp/get_dashboard_data",
        headers=header,
        data=json.dumps(master_payload),
        cookies=config.get("configurable", {}).get("cookie"),
    )

    # Check if the request was successful
    if response.status_code == 200:
        # Parse the JSON response
        results = response.json().get("data", {})
        for key in results:
            results[key] = [
                {"id": item["id"], "name": item["name"]}
                for item in results[key]
                if item.get("id")
            ]

    else:
        # Handle errors
        raise Exception(f"Error fetching data: {response.status_code}")

    return results


@tool
def fetch_sales_analytics(
    from_date: str,
    to_date: str,
    analysis_type: str,
    branch: list[int],
    config: RunnableConfig,
) -> Dict:
    """
    Retrieve detailed sales analytics for a given date range, with optional filters for branch and customer-specific breakdowns.

    This function supports various sales analysis types, such as total credit and cash sales, customer-level breakdowns, and sales comparisons (yearly, monthly, or quarterly). You can also filter the analysis by specific branches or customers.

    Args:
        from_date (str): The start date for the analysis period, formatted as 'DD-MM-YYYY'.
        to_date (str): The end date for the analysis period, formatted as 'DD-MM-YYYY'.
        analysis_type (str): Specifies the type of sales analysis to be performed. Supported values include:
            - "TOTAL CREDIT SALES": Total credit sales within the specified period.
            - "TOTAL CASH SALES": Total cash sales within the specified period.
            - "CASH SALES BY BRANCH OR CUSTOMER": Cash sales breakdown by branch or customer.
            - "CREDIT SALES BY BRANCH OR CUSTOMER": Credit sales breakdown by branch or customer.
            - "TOTAL SALES COMPARISON": Overall sales comparison by year, month, or quarter.
            - "CASH SALES OF SPECIFIC BRANCH": Cash sales for a specific branch.
            - "CREDIT SALES OF SPECIFIC BRANCH": Credit sales for a specific branch.
            - "CREDIT SALES OF SPECIFIC BRANCH CUSTOMERS": Credit sales for customers of a specific branch.
            - "CASH SALES OF SPECIFIC BRANCH CUSTOMERS": Cash sales for customers of a specific branch.
            - "SALES COMPARISON SPECIFIC BRANCH": Sales comparison for a specific branch, by year, month, or quarter.
            - "REFUND OR VOID SALES": Analytics for refund or void sales.
        branch_ids (list[int], optional): A list of branch IDs to filter the analysis to specific branches. If not provided, the analysis will cover all branches.

    Returns:
        dict: A structured dictionary containing the requested sales analytics data, organized by the specified parameters.

    Example:
        sales_data = get_sales_analytics("01-01-2025", "31-01-2025", "TOTAL CREDIT SALES", branch_ids=[1, 2])
        # Returns a dictionary with total credit sales data for branches 1 and 2 in January 2025.
    """

    # Example API endpoint
    url = config.get("configurable", {}).get("domain")

    dct_sales_analytics_payload = {
        "TOTAL CREDIT SALES": {
            "category": ["fop"],
            "combine_txn": ["fop"],
            "module": "fop",
            "dashboard": "Sales Analytics",
            "filter": {"fop": ["CREDIT"]},
            "txn_filter": {"fop": ["CLIENT"]},
        },
        "TOTAL CASH SALES": {
            "category": ["fop"],
            "combine_txn": ["fop"],
            "module": "fop",
            "dashboard": "Sales Analytics",
            "filter": {"fop": ["CASH", "CHEQUE", "CC POS", "CC DIRECT"]},
            "txn_filter": {
                "fop": [
                    "CASH",
                    "PETTY CASH",
                    "BANK",
                    "DEBIT CARD",
                    "CREDIT CARD",
                    "CHEQUE",
                    "PDC RECEIVED",
                ]
            },
        },
        "CASH SALES BY BRANCH OR CUSTOMER": {
            "category": ["branch", "customer"],
            "module": "fop",
            "dashboard": "Sales Analytics",
            "filter": {"fop": ["CASH", "CHEQUE", "CC POS", "CC DIRECT"]},
        },
        "CREDIT SALES BY BRANCH OR CUSTOMER": {
            "category": ["branch", "customer"],
            "module": "fop",
            "dashboard": "Sales Analytics",
            "filter": {"fop": ["CREDIT"]},
        },
        "TOTAL SALES COMPARISON": {
            "category": ["month", "year", "quarter"],
            "combine_txn": ["month", "year"],
            "module": "all",
            "dashboard": "Sales Analytics",
            "filter": {},
            "txn_filter": {
                "fop": [
                    "CLIENT",
                    "CASH",
                    "PETTY CASH",
                    "BANK",
                    "DEBIT CARD",
                    "CREDIT CARD",
                    "CHEQUE",
                    "PDC RECEIVED",
                ]
            },
        },
        "CASH SALES OF SPECIFIC BRANCH": {
            "category": ["fop"],
            "combine_txn": ["fop"],
            "module": "fop",
            "dashboard": "Sales Analytics",
            "filter": {
                "fop": ["CASH", "CHEQUE", "CC POS", "CC DIRECT"],
                "branch": branch,
            },
            "txn_filter": {
                "fop": [
                    "CASH",
                    "PETTY CASH",
                    "BANK",
                    "DEBIT CARD",
                    "CREDIT CARD",
                    "CHEQUE",
                    "PDC RECEIVED",
                ],
                "branch": branch,
            },
        },
        "CREDIT SALES OF SPECIFIC BRANCH": {
            "category": ["fop"],
            "combine_txn": ["fop"],
            "module": "fop",
            "dashboard": "Sales Analytics",
            "filter": {"fop": ["CREDIT"], "branch": branch},
            "txn_filter": {"fop": ["CLIENT"], "branch": branch},
        },
        "CREDIT SALES OF SPECIFIC BRANCH CUSTOMERS": {
            "category": ["customer"],
            "module": "fop",
            "dashboard": "Sales Analytics",
            "filter": {"fop": ["CREDIT"], "branch": branch},
        },
        "CASH SALES OF SPECIFIC BRANCH CUSTOMERS": {
            "category": ["customer"],
            "module": "fop",
            "dashboard": "Sales Analytics",
            "filter": {
                "fop": ["CASH", "CHEQUE", "CC POS", "CC DIRECT"],
                "branch": branch,
            },
        },
        "SALES COMPARISON SPECIFIC BRANCH": {
            "category": ["month", "year", "quarter"],
            "combine_txn": ["month", "year"],
            "module": "all",
            "dashboard": "Sales Analytics",
            "filter": {},
            "txn_filter": {
                "fop": [
                    "CLIENT",
                    "CASH",
                    "PETTY CASH",
                    "BANK",
                    "DEBIT CARD",
                    "CREDIT CARD",
                    "CHEQUE",
                    "PDC RECEIVED",
                ],
                "branch": branch,
            },
        },
        "REFUND OR VOID SALES": {
            "category": ["status"],
            "module": "all",
            "dashboard": "branch",
            "filter": {},
        },
    }
    sales_payload = {
        "from_date": from_date,
        "to_date": to_date,
        "sort_by": "current_period_sales",
        **dct_sales_analytics_payload[analysis_type],
    }
    logging.info(sales_payload)
    # Make the API request
    response = requests.request(
        "GET",
        url + "/api/mobApp/get_dashboard_data",
        headers=header,
        data=json.dumps(sales_payload),
        cookies=config.get("configurable", {}).get("cookie"),
    )

    # Check if the request was successful
    if response.status_code == 200:
        # Parse the JSON response
        results = response.json().get("data")
    else:
        # Handle errors
        raise Exception(f"Error fetching data: {response.status_code}")

    return results


@tool
def fetch_cash_bank_balance(
    from_date: str,
    to_date: str,
    categories: List[str],
    balance_types: List[str],
    config: RunnableConfig,
) -> Dict:
    """
    Retrieve the transaction balance to provide insights into the company's financial liquidity over a specified date range.

    This function allows you to view and analyze the company's balance data, grouped by different categories and balance types. The analysis can span various financial dimensions such as branch, bank accounts, transaction status, and form of payment.

    Args:
        from_date (str): The start date for the balance analysis, formatted as 'DD-MM-YYYY'.
        to_date (str): The end date for the balance analysis, formatted as 'DD-MM-YYYY'.
        categories (List[str]): A list of categories to group the balance data by. Supported values include:
            - "branch": Group by company branches.
            - "account": Group by bank accounts.
            - "status": Group by transaction status, such as void (V) or refund (R).
            - "fop": Group by form of payment, such as CREDIT or CASH.
        balance_types (List[str]): A list of balance types to include in the analysis. Supported values include:
            - "CASH": In-hand cash balance.
            - "PETTY CASH": Cash reserved for small, day-to-day expenses.
            - "BANK": Balances in company bank accounts.

    Returns:
        dict: A structured dictionary containing the categorized balance details for the specified date range.
    """

    url = config.get("configurable", {}).get("domain")

    bank_balance_payload = {
        "from_date": from_date,
        "to_date": to_date,
        "category": categories,
        "module": "transaction",
        "dashboard": "Cash and Bank Balance",
        "filter": {"fop": balance_types},
        "sort_by": "current_period_revenue",
    }
    logging.info(bank_balance_payload)
    # Make the API request
    try:
        response = requests.request(
            "GET",
            url + "/api/mobApp/get_dashboard_data",
            headers=header,
            data=json.dumps(bank_balance_payload),
            cookies=config.get("configurable", {}).get("cookie"),
        )
    except Exception as ex:
        print(str(ex))

    # Check if the request was successful
    if response.status_code == 200:
        # Parse the JSON response
        results = response.json().get("data", {})
        # Process the data as needed
    else:
        # Handle errors
        raise Exception(f"Error fetching data: {response.status_code}")

    return results


@tool
def transaction_revenue_and_expense(
    from_date: str, to_date: str, bln_account: bool, type: str, config: RunnableConfig
) -> Dict:
    """
    Retrieves account transaction or revenue data within a specified date range.

    Args:
        from_date (str): Start date in 'DD-MM-YYYY' format.
        to_date (str): End date in 'DD-MM-YYYY' format.
        bln_account (bool): Flag to indicate whether to fetch account-specific transactions.
        type (str): Specifies the type of data to fetch. Valid options are:
            - "TRANSACTIONS": Account transaction details.
            - "REVENUE": Total revenue within the period.
            - "CREDIT REVENUE": Revenue from credit transactions.
            - "CASH REVENUE": Revenue from cash transactions.

    Returns:
        dict: A dictionary containing the requested transaction or revenue data.
    """

    url = config.get("configurable", {}).get("domain")
    dct_filter_type = {
        "TRANSACTIONS": ["INCOME", "EXPENSE"],
        "REVENUE": ["INCOME"],
        "CREDIT REVENUE": ["CLIENT"],
        "CASH REVENUE": [
            "CASH",
            "PETTY CASH",
            "BANK",
            "DEBIT CARD",
            "CREDIT CARD",
            "CHEQUE",
            "PDC RECEIVED",
        ],
    }
    account_transaction_payload = {
        "from_date": from_date,
        "to_date": to_date,
        "category": ["account"] if bln_account else ["total"],
        "module": "transaction",
        "dashboard": "transaction",
        "filter": {"fop": dct_filter_type[type]},
        "sort_by": "current_period_revenue",
    }
    logging.info(account_transaction_payload)
    # Make the API request
    try:
        response = requests.request(
            "GET",
            url + "/api/mobApp/get_dashboard_data",
            headers=header,
            data=json.dumps(account_transaction_payload),
            cookies=config.get("configurable", {}).get("cookie"),
        )
    except Exception as ex:
        print(str(ex))

    # Check if the request was successful
    if response.status_code == 200:
        # Parse the JSON response
        data = response.json()
        # Process the data as needed
        results = data.get("data", {})
    else:
        # Handle errors
        raise Exception(f"Error fetching data: {response.status_code}")

    return results


@tool
def uncleared_transaction(
    from_date: str, to_date: str, config: RunnableConfig
) -> List[Dict]:
    """
    Fetches all uncleared transactions (i.e., bank reconciliation not yet completed) within a specified date range.

    Args:
        from_date (str): The beginning date of the transaction period in DD-MM-YYYY format.
        to_date (str): The ending date of the transaction period in DD-MM-YYYY format.

    Returns:
        list: A list of uncleared transactions within the provided date range.
    """

    url = config.get("configurable", {}).get("domain")

    account_transaction_payload = {
        "from_date": from_date,
        "to_date": to_date,
        "category": ["fop"],
        "module": "transaction",
        "dashboard": "Cash and Bank Balance",
        "filter": {
            "fop": ["DEBIT CARD", "CREDIT CARD", "CHEQUE"],
            "cleared": ["FALSE"],
        },
        "sort_by": "current_period_revenue",
    }

    # Make the API request
    try:
        response = requests.request(
            "GET",
            url + "/api/mobApp/get_dashboard_data",
            headers=header,
            data=json.dumps(account_transaction_payload),
            cookies=config.get("configurable", {}).get("cookie"),
        )
    except Exception as ex:
        print(str(ex))

    # Check if the request was successful
    if response.status_code == 200:
        # Parse the JSON response
        data = response.json()
        # Process the data as needed
        results = data.get("data", {}).get("fop", [])
    else:
        # Handle errors
        raise Exception(f"Error fetching data: {response.status_code}")

    return results


@tool
def not_reported_sales(
    from_date: str, to_date: str, config: RunnableConfig
) -> List[Dict]:
    """
    Fetches all not reported sales within a specified date range.

    Args:
        from_date (str): The beginning date of the sale period in DD-MM-YYYY format.
        to_date (str): The ending date of the sale period in DD-MM-YYYY format.

    Returns:
        list: A list of not reported sales within the provided date range.
    """

    url = config.get("configurable", {}).get("domain")
    not_reported_sales_payload = {
        "from_date": from_date,
        "to_date": to_date,
        "category": ["not_reported_service"],
        "module": "not_reported_sales",
        "dashboard": "Not Reported Sales",
        "sort_by": "current_period_sales",
    }

    # Make the API request
    try:
        response = requests.request(
            "GET",
            url + "/api/mobApp/get_dashboard_data",
            headers=header,
            data=json.dumps(not_reported_sales_payload),
            cookies=config.get("configurable", {}).get("cookie"),
        )
    except Exception as ex:
        print(str(ex))

    # Check if the request was successful
    if response.status_code == 200:
        # Parse the JSON response
        data = response.json()
        # Process the data as needed
        results = data.get("data", {}).get("not_reported_service", [])
    else:
        # Handle errors
        raise Exception(f"Error fetching data: {response.status_code}")

    return results


@tool
def profit_loss_analyse(
    from_date: str, to_date: str, type: str, config: RunnableConfig
) -> Dict:
    """
    Retrieves profit and loss analysis for a specified date range, with multiple breakdown options.

    This function provides detailed insights including:
    - Branch-wise and total profit and loss
    - Service-wise profit and loss (e.g., TICKET, HOTEL, OTHER)
    - Profit and loss comparisons by year, month, or quarter
    - A summary of expenditures within the selected period

    Args:
        from_date (str): Start date of the analysis period in 'DD-MM-YYYY' format.
        to_date (str): End date of the analysis period in 'DD-MM-YYYY' format.
        type (str): Type of analysis to perform. Supported values:
            - "BRANCH": Branch-wise and total profit and loss analysis.
            - "SERVICES": Service-wise profit and loss (TICKET, HOTEL, OTHER).
            - "COMPARE": Yearly, monthly, or quarterly profit and loss comparison.
            - "EXPENDITURE": Summary of expenditures during the period.
    Returns:
        Dictionary containing profit and loss analysis for a specified date range.

    """

    url = config.get("configurable", {}).get("domain")
    dct_type_payload = {
        "SERVICES": {
            "category": ["all_services"],
            "combine_txn": ["all_services"],
            "module": "all",
            "dashboard": "P & L Summary",
            "filter": {},
            "txn_filter": {"fop": ["INCOME"]},
            "sort_by": "current_period_sales",
        },
        "BRANCH": {
            "category": ["total", "branch"],
            "module": "transaction",
            "dashboard": "P & L Summary",
            "filter": {"fop": ["INCOME", "EXPENSE"]},
            "sort_by": "current_period_revenue",
        },
        "COMPARE": {
            "category": ["year", "month", "quarter"],
            "module": "transaction",
            "dashboard": "P & L Summary",
            "filter": {"fop": ["INCOME", "EXPENSE"]},
            "sort_by": "current_period_revenue",
        },
        "EXPENDITURE": {
            "category": ["account"],
            "module": "transaction",
            "dashboard": "P & L Summary",
            "filter": {"fop": ["EXPENSE"]},
            "sort_by": "current_period_revenue",
        },
    }
    profil_loss_payload = {
        "from_date": from_date,
        "to_date": to_date,
        **dct_type_payload[type],
    }
    logging.info(profil_loss_payload)
    # Make the API request
    try:
        response = requests.request(
            "GET",
            url + "/api/mobApp/get_dashboard_data",
            headers=header,
            data=json.dumps(profil_loss_payload),
            cookies=config.get("configurable", {}).get("cookie"),
        )
    except Exception as ex:
        print(str(ex))

    # Check if the request was successful
    if response.status_code == 200:
        # Parse the JSON response
        data = response.json()
        # Process the data as needed
        results = data.get("data", {})
        logging.info(results)
    else:
        # Handle errors
        raise Exception(f"Error fetching data: {response.status_code}")

    return results


@tool
def fetch_service_analytics(
    from_date: str, to_date: str, config: RunnableConfig
) -> Dict:
    """
    Retrieves sales analysis data for different service types (TICKET, HOTEL, CAR, OTHER) within a specified date range.
    It returns the total counts and sales for each service category, helping to assess performance for the given period.

    Args:
        from_date (str): The start date of the sales period in 'DD-MM-YYYY' format.
        to_date (str): The end date of the sales period in 'DD-MM-YYYY' format.

    Returns:
        dict: A dictionary containing the segmented sales data for each service type (TICKET, HOTEL, CAR, OTHER).
              The data includes the count of transactions and total sales for each category within the provided date range.
    """

    url = config.get("configurable", {}).get("domain")
    results = {}
    service_payload = {
        "from_date": from_date,
        "to_date": to_date,
        "category": ["all_services"],
        "module": "all",
        "dashboard": "Service Analytics",
        "sort_by": "current_period_sales",
    }
    logging.info(service_payload)
    # Make the API request
    try:
        response = requests.request(
            "GET",
            url + "/api/mobApp/get_dashboard_data",
            headers=header,
            data=json.dumps(service_payload),
            cookies=config.get("configurable", {}).get("cookie"),
        )
    except Exception as ex:
        print(str(ex))

    # Check if the request was successful
    if response.status_code == 200:
        # Parse the JSON response
        data = response.json()
        # Process the data as needed
        results = data.get("data", {})
    else:
        # Handle errors
        raise Exception(f"Error fetching data: {response.status_code}")

    return results


@tool
def fetch_ageing_overdue_report(
    config: RunnableConfig, report_type: str, customer_id: Optional[int] = None
) -> Dict:
    """
    Retrieves financial and credit-related ageing reports by dynamically constructing
    based on the specified business insight type.

    Args:
        report_type (str): Type of financial insight to retrieve. Supported options include:
            - "Customer Debt Ageing": Provides a detailed ageing report of outstanding balances per customer,
            categorized by monthly time buckets (e.g., Mar 2025, Feb 2025) and a total balance. Useful for
            tracking receivables and analyzing customer payment patterns over time.

            - "Debt Ageing by Debtor Type": Returns a summarized view of balances grouped by debtor types
            (e.g., departments, branches, customer segments), showing current and overdue amounts. Helps
            assess credit exposure and inform collection strategies.

            - "Credit and Overdue Details By Specific Customer": Retrieves the credit profile of a specific customer,
            including credit limit, credit terms (in days), and overdue balances. Supports credit risk
            evaluation and credit limit enforcement.

            - "Overdue Ageing Summary Specific Customer": Presents overdue balances for a specific customer across
            day-based ageing buckets (e.g., 15D, 30D, 60D, 90D, 120D+). Assists in prioritizing collections
            and monitoring account-level risk.

        customer_id (int, optional): Required for customer-specific reports ("Credit and Overdue Details By Specific Customer"
            and "Overdue Ageing Summary Specific Customer"). Must be a valid customer ID.

    Returns:
        dict: A dictionary containing the requested financial or credit-related ageing report.

    """

    # Example API endpoint
    url = config.get("configurable", {}).get("domain")

    dct_ageing_payload = {
        "Customer Debt Ageing": {
            "category": ["customer"],
            "module": "ageing",
            "dashboard": "ageing",
            "filter": {},
            "sort_by": "dbl_balance",
            "strAgeingPeriod": "total",
            "intDebtorTypeId": 0,
            "intDebtorGroupId": 0,
            "lstAgeingPeriod": ["1 M", "2 M", "3 M", "4 M", "5 M", "6 M", "7 M"],
            "blnAutoMatch": False,
            "strCustomerId": 0,
        },
        "Debt Ageing by Debtor Type": {
            "category": ["debtor_type"],
            "module": "ageing",
            "dashboard": "ageing",
            "filter": {},
            "sort_by": "dbl_balance",
            "strAgeingPeriod": "7 M",
            "intDebtorTypeId": 0,
            "intDebtorGroupId": 0,
            "lstAgeingPeriod": ["1 M", "2 M", "3 M", "4 M", "5 M", "6 M", "7 M"],
            "blnAutoMatch": False,
            "strCustomerId": 0,
        },
        "Credit and Overdue Details By Specific Customer": {
            "category": ["client"],
            "module": "ageing",
            "dashboard": "ageing",
            "strCustomerId": customer_id,
        },
        "Overdue Ageing Summary Specific Customer": {
            "category": ["customer"],
            "module": "ageing",
            "dashboard": "ageing",
            "filter": {},
            "sort_by": "dbl_balance",
            "strAgeingPeriod": "total",
            "intDebtorTypeId": 0,
            "intDebtorGroupId": 0,
            "lstAgeingPeriod": ["15 D", "30 D", "60 D", "90 D", "120 D"],
            "blnAutoMatch": True,
            "strCustomerId": customer_id,
        },
    }
    ageing_payload = dct_ageing_payload[report_type]
    logging.info(ageing_payload)
    # Make the API request
    response = requests.request(
        "GET",
        url + "/api/mobApp/get_dashboard_data",
        headers=header,
        data=json.dumps(ageing_payload),
        cookies=config.get("configurable", {}).get("cookie"),
    )

    # Check if the request was successful
    if response.status_code == 200:
        # Parse the JSON response
        results = response.json().get("data")
    else:
        # Handle errors
        raise Exception(f"Error fetching data: {response.status_code}")

    return results


@tool
def get_plb_details(config: RunnableConfig) -> Dict:
    """
    Fetches Productivity Linked Bonus (PLB) details for the airline and travel industry. PLB is a performance-based incentive offered by airlines to travel agencies based on ticket sales volume or value.
    PLB Summary Includes:
        - **List of Airlines**:
        Displays all airlines with active PLB agreements, offering a snapshot of airline-specific performance.

        - **Tenure**:
        Shows the validity period for achieving PLB targets, helping agencies plan sales strategies within the incentive window.

        - **Target**:
        Lists sales targets set by each airline to qualify for PLB incentives, aligning agency efforts with airline expectations.

        - **Probability**:
        Estimates the likelihood of achieving PLB targets within the tenure, using historical trends and current sales data.

    Returns:
        Dictionary containing Productivity Linked Bonus (PLB) details.

    """

    url = config.get("configurable", {}).get("domain")
    results = {}
    plb_payload = {
        "strPlbId": "",
        "strSlab": "",
        "airline_id": "",
        "dashboard": "PLB",
        "module": "plb",
        "category": ["plb"],
    }

    logging.info(plb_payload)

    # Make the API request
    try:
        response = requests.request(
            "GET",
            url + "/api/mobApp/get_dashboard_data",
            headers=header,
            data=json.dumps(plb_payload),
            cookies=config.get("configurable", {}).get("cookie"),
        )
    except Exception as ex:
        logging.error(ex)
        return {}

    # Check if the request was successful
    if response.status_code == 200:
        # Parse the JSON response
        data = response.json()
        # Process the data as needed
        results = data.get("data", {})
        logging.info(f"lenght is {len(json.dumps(results))}")
    else:
        # Handle errors
        logging.error(response.status_code)

    return results


__all__ = [
    "fetch_master_info",
    "fetch_sales_analytics",
    "fetch_cash_bank_balance",
    "transaction_revenue_and_expense",
    "uncleared_transaction",
    "not_reported_sales",
    "profit_loss_analyse",
    "fetch_service_analytics",
    "fetch_ageing_overdue_report",
    "get_plb_details",
]
