import httpx
import traceback
from langchain_core.tools import tool
from typing import TypedDict,List, Dict ,Optional
from langchain_core.runnables import RunnableConfig
from app.utils.secureconfig import ConfigParserCrypt
from app.utils.conf_path import str_configpath
from app.utils.global_config import env_mode


ins_cfg = ConfigParserCrypt()
ins_cfg.read(str_configpath)
NUHIVE_URL = ins_cfg.get(env_mode, 'NUHIVE_URL')

class SprintDetails(TypedDict):
    intSprintId: int
    strSprintName: str
class Projects(TypedDict):
    pk_bint_project_id: int
    vchr_project_name: str
class IssueStatus(TypedDict):
    intIssueId: int
    strIssueName: str
class IssueType(TypedDict):
    pk_bint_issue_type_id: int
    vchr_issue_type: str
    vchr_issue_description: str
class Assignee(TypedDict):
    intUserId: int
    vchr_login_name: str
    strAssignee: str

class Priority(TypedDict):
    intPk: int
    strName: str
    strDescription: str
    
class Customers(TypedDict):
    intPk: int
    strCustomerName: str
class IssueMetadata(TypedDict):
    issue_statuses: List[IssueStatus]
    issue_types: List[IssueType]
    assignees: List[Assignee]
    priorities: List[Priority]
    customers: List[Customers]
    
class GetFilteredIssueStatus(TypedDict):
    intIssueId : int
    intSprintId :int
    strSprintName :str
    strIssueKey : str    

async def get_sprint_details(
    config: RunnableConfig,
    project : Projects
    ) -> SprintDetails:
    """
    Retrieve sprint details for a given project, specifically the sprint named "BACKLOG".

    Args:
        config (RunnableConfig): Configuration for the current session, including authentication token.
        project (Projects): The project for which to retrieve sprint details. Must be selected
                            from the list returned by `get_projects()`.
    Returns:
        SprintDetails: A dictionary containing the sprint details with the following fields:
            - intSprintId (int): The unique ID of the sprint.
            - strSprintName (str): The name of the sprint (typically "BACKLOG").
    """
    
    url = f"{NUHIVE_URL}/api/masters/get_sprint_details"
    token = config.get('configurable', {}).get('token')
    payload = {"objPagination":{"intPerPage":0,"intPageOffset":0,"intTotalCount":0},"intProjectId":project.get("pk_bint_project_id"),"objFilter":{"arrUserId":[],"arrType":[],"intIssueid":0,"arrStatus":[],"strSortBy":""}}
    
    header = {
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br",
            "Origin":f"{NUHIVE_URL}",
            "Referer":f"{NUHIVE_URL}/",
            "X-Access-Token": f"Bearer {token}"
        }
    async with httpx.AsyncClient() as client:
        response = await client.post(url=url,headers=header,json=payload)
        for data in response.json()['arrList']:
            if data["strProjectName"] == f"{project.get("vchr_project_name")}" and data["strSprintName"] == "BACKLOG":
                dct_backlog_details = {
                        "intSprintId" : data["intSprintId"],
                        "strSprintName": data["strSprintName"]
                    }
                return dct_backlog_details
    
@tool
async def get_projects(
    config: RunnableConfig
    ) -> List[Projects]:
    
    """
    Fetch a list of available projects(application) that the user has access to.
    
    Args:
        config (RunnableConfig): Configuration for the current session, including authentication token.

    Returns:
        List[Projects]: A list of dictionaries, each representing a project with the following fields:
            - pk_bint_project_id (int): The unique ID of the project.
            - vchr_project_name (str): The name of the project.
    """
    
    url = f"{NUHIVE_URL}/api/utils/get_dropdown"
    token = config.get('configurable', {}).get('token')
    
    header = {
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br",
            "Origin":f"{NUHIVE_URL}",
            "Referer":f"{NUHIVE_URL}/",
            "X-Access-Token": f"Bearer {token}"
        }
    payload = {"strDropdownKey" : "PROJECTS"}
    async with httpx.AsyncClient() as client:
        response = await client.post(url=url ,headers=header, json=payload)
        projects=[]
        for item in response.json():
            projects.append({
                "pk_bint_project_id":item["pk_bint_project_id"],
                "vchr_project_name" : item["vchr_project_name"],
                })
        return projects
    
@tool
async def get_issue_metadata(
    config: RunnableConfig,
    project : Projects) -> IssueMetadata:
    
    """
    Fetch metadata required for issue creation such as statuses, types, assignees, priorities, and customers.

    Args:
        config (RunnableConfig):  Configuration for the current session, including authentication token.
        intProjectId (int): The ID of the selected project(app) for which metadata is being fetched.

    Returns:
        IssueMetadata: A dictionary containing metadata options for issue creation.
            Includes the following keys:

            - issue_statuses (List[str]): List of available issue statuses 
              (e.g., "To Do", "In Progress", "Done", etc.).
            
            - issue_types (List[str]): List of available issue types 
              (e.g., "Bug", "Task", "Story", "IT Admin Support (Internal)", 
              "CSG (Customer Support)", etc.).
            
            - assignees (List[str]): List of eligible user names that can be assigned to issues.
            
            - priorities (List[str]): List of priority levels 
              (e.g., "Critical", "High", "Medium", "Low").
            
            - customers (List[str]): List of customers to whom the issue may be related.
    """
    try:
        
        url = f"{NUHIVE_URL}/api/utils/get_dropdown"
        token = config.get('configurable', {}).get('token')

        # Common headers
        base_headers = {
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br",
            "Origin": f"{NUHIVE_URL}",
            "Referer": f"{NUHIVE_URL}/",
            "X-Access-Token": f"Bearer {token}"
        }

        # === Fetch Issue Statuses ===
        dct_payload_status = {"strDropdownKey": "ISSUE_STATUS"}
        async with httpx.AsyncClient() as client:
            response_status = await client.post(url=url, headers=base_headers, json=dct_payload_status)
            issue_statuses = []
            if response_status.status_code == 200:
                for item in response_status.json():
                    issue_statuses.append({
                        "intIssueId": item["intIssueId"],
                        "strIssueName": item["strIssueName"]
                    })

        # === Fetch Issue Types ===
        dct_payload_type = {"strDropdownKey": "ISSUE_TYPE"}
        async with httpx.AsyncClient() as client:
            response_type = await client.post(url=url, headers=base_headers, json=dct_payload_type)
            issue_types = []
            if response_type.status_code == 200:
                for item in response_type.json():
                    issue_types.append({
                        "pk_bint_issue_type_id": item["pk_bint_issue_type_id"],
                        "vchr_issue_type": item["vchr_issue_type"],
                        "vchr_issue_description": item["vchr_issue_description"]
                    })

        # === Fetch Assignees ===
        headers_assignee = dict(base_headers)
        headers_assignee["intpluginid"] = "1"
        dct_payload_assignee = {"strDropdownKey": "USER"}
        async with httpx.AsyncClient() as client:
            response_assignee = await client.post(url=url, headers=headers_assignee, json=dct_payload_assignee)
            assignees = []
            if response_assignee.status_code == 200:
                for item in response_assignee.json():
                    assignees.append({
                        "intUserId": item["intUserId"],
                        "vchr_login_name": item["vchr_login_name"],
                        "strAssignee": item["strAssignee"]
                    })

        # === Fetch Priorities ===
        dct_payload_priority = {"strDropdownKey": "PRIORITY"}
        async with httpx.AsyncClient() as client:
            response_priority = await client.post(url=url, headers=base_headers, json=dct_payload_priority)
            priorities = []
            if response_priority.status_code == 200:
                for item in response_priority.json():
                    priorities.append({
                        "intPk": item["intPk"],
                        "strName": item["strName"],
                        "strDescription": item["strDescription"]
                    })
                
        # === Fetch Customer Details ===    
        dct_payload_customers = {"strDropdownKey": "PROJECT_CUSTOMERS", "intProjectId": project.get("pk_bint_project_id")}
        async with httpx.AsyncClient() as client:
            response_customers = await client.post(url=url, headers=headers_assignee, json=dct_payload_customers)
            customers =[]
            if response_customers.status_code == 200:
                for item in response_customers.json():
                    customers.append({
                        "intPk":item["intPk"],
                        "strCustomerName":item["strCustomerName"]
                    })
        return {
            "issue_statuses": issue_statuses,
            "issue_types": issue_types,
            "assignees": assignees,
            "priorities": priorities,
            "customers": customers
        }
        
    except Exception:
        traceback.print_exc()

@tool
async def get_filtered_issue_statuses(
    config: RunnableConfig,
    project : Projects) -> List[GetFilteredIssueStatus]:
    """
    Retrieves the working status of issues based on user-defined conditions.

    This function fetches a list of issues and their current working statuses, 
    such as "To Do", "In Progress", or "Done", according to user-defined filters.
    
    Args:
        config (RunnableConfig): Configuration for the runtime.
        intProjectId (Projects): The project id(app id) for which to retrieve issue statuses.
        
    Returns:
        List[GetAllIssueStatus]: A list of issues with their working status
    """
    try:
        url = f"{NUHIVE_URL}/api/masters/get_all_created_issues"
        payload = {"objPagination":{"intPerPage":0,"intPageOffset":0,"intTotalCount":0},"intProjectId":project.get("pk_bint_project_id"),"objFilter":{"arrUserId":[],"arrType":[],"intIssueid":0,"arrStatus":[],"strSortBy":""}}
        header = {
                "Content-Type": "application/json",
                "Accept": "*/*",
                "intpluginid" : "1",
                "Accept-Encoding": "gzip, deflate, br",
                "Origin":f"{NUHIVE_URL}",
                "Referer":f"{NUHIVE_URL}/",
                "X-Access-Token": f"Bearer {config.get('configurable', {}).get('token')}"
            }
        async with httpx.AsyncClient() as client:
            response = await client.post(url=url,headers=header,json=payload)
            lst_all_issue_status =[]
            for data in response.json()['arrList']:
                dct_response = {
                    "intIssueId" : data["intIssueId"],
                    "intSprintId" : data["intSprintId"],
                    "strSprintName" : data["strSprintName"],
                    "strIssueName" : data["strIssueName"],
                    "strIssueKey" : data["strIssueKey"]
                }
                lst_all_issue_status.append(dct_response)
            
        return lst_all_issue_status
    except Exception:
        traceback.print_exc()

@tool
async def create_issue(
    summry: str,
    config: RunnableConfig,
    customer :Customers,
    project : Projects,
    assignee : Optional[Assignee] = None,
    priority : Optional[Priority] = None,
    issuetype : Optional[IssueType] = None
    ) -> List[Dict]:
    
    
    """
    Create a new issue in the Nuhive system.
    Use `get_issue_metadata()` to retrieve the latest valid options for each field and validate them before proceed. 

    Args:
        summry (str): Brief description or summary of the issue.
        config (RunnableConfig): Runtime configuration context.
        customer (Customers): Customer related to the issue (mandatory).
        project (Projects): The project (or application) the issue belongs to.
        assignee (Optional[Assignee]): Person assigned to the issue.
        priority (Optional[Priority]): Priority level of the issue.
        issuetype (Optional[IssueType]): Type/category of the issue.

    Returns:
        List[Dict]: A list of dictionary containing the created issue's details .
    """

    try:
        # print("issuetype.get('pk_bint_issue_type_id') if issuetype else None",issuetype.get('pk_bint_issue_type_id') if issuetype else None)
        # print("issuestatus.get('intIssueId') if issuetype else 1",issuestatus.get('intIssueId') if issuetype else 1)
        # print("priority.get('intPk') if priority else 2",priority.get('intPk') if priority else 2)
        # print("issuestatus",issuestatus)
        sprint = await get_sprint_details(config, project)
        
        url= f"{NUHIVE_URL}/api/masters/create_issue"
        payload = {
            "intProjectId": project.get("pk_bint_project_id"),
            "intIssueType": issuetype.get('pk_bint_issue_type_id') if issuetype else 2,
            "intStatus": 1,
            "strSummary": summry,
            "strDescription": "",
            "intPriority": priority.get('intPk') if priority else 2,
            "intSprintPeriod":sprint["intSprintId"],
            "intParentId": 0,
            "timEstimation": 120,
            "intAssigneeId": assignee.get('intUserId') if assignee else 15,
            "intCustomerId": customer.get('intPk') if customer else None,
            "intModuleId": "",
            "intEpicId": "",
            "intReleaseId": "",
            "jsonCustomField": [
                {
                "intIssuesId": [
                    9,
                    6,
                    12,
                    1,
                    3,
                    2,
                    4,
                    11,
                    13,
                    5,
                    10
                ],
                "value": "",
                "strWidgetDataType": "Text",
                "blnShow": True,
                "strWidgetName": "",
                "strName": "Source",
                "strWidgetLabel": "",
                "blnMandatory": False,
                "blnVisibility": False,
                "arrOptions": [],
                "intPk": 26,
                "blnAllProjects": False,
                "arrPredefindOptions": [],
                "predefindValue": ""
                },
                {
                "intIssuesId": [
                    5,
                    3,
                    2,
                    1,
                    9,
                    6,
                    11,
                    10,
                    12
                ],
                "value": "",
                "strWidgetDataType": "Text",
                "blnShow": True,
                "strWidgetName": "strMandatoryF",
                "strName": "Mandatory F",
                "strWidgetLabel": "LABELS.MANDATORY_F",
                "blnMandatory": False,
                "blnVisibility": False,
                "arrOptions": [],
                "intPk": 55,
                "blnAllProjects": True,
                "arrPredefindOptions": [],
                "predefindValue": ""
                }
            ],
            "intSprintId": sprint["intSprintId"],
            "intKanbanId": "",
            "arrAttachment": [],
            "arrCheckList": [],
            "arrCreateAttachments": [],
            "str_origin": f"{NUHIVE_URL}"
            }

        header = {
                "Content-Type": "application/json",
                "Accept": "*/*",
                "Accept-Encoding": "gzip, deflate, br",
                "Origin":f"{NUHIVE_URL}",
                "Referer":f"{NUHIVE_URL}/",
                "X-Access-Token": f"Bearer {config.get('configurable', {}).get('token')}"
            }
        async with httpx.AsyncClient() as client:
            response = await client.post(url=url,headers=header,json=payload)
            return [{"message": "Issue created successfully", "data": response.json()}]
        
    except Exception:
        traceback.print_exc()

__all__ = ["create_issue","get_issue_metadata","get_filtered_issue_statuses","get_projects"]