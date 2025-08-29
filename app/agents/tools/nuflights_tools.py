import logging
import traceback
import asyncio
import json
from langchain_core.tools import tool
from datetime import datetime
from langchain_core.runnables import RunnableConfig
from typing import List, Dict
from app.agents.helpers.nuflights_queries import (
    search_by_od_query,
    offer_price_query,
    order_ticket_query
)
from app.agents.helpers.nuflights_helpers import (
    PaxCount,
    FlightTicket,
    PaxDeatils,
    TravelDetails,
    call_nuflights_api,
    generate_pax_by_count,
    get_ticket_search_variables,
    process_all_offers,
    get_pax_details,
    get_contact_details,
    get_priced_offer_variable,
    get_ticket_order_variable,
    send_eticket_via_email,
    send_eticket_via_whatsapp,
    process_offer_combinations,
    restructure_offers
)


# Configure logging to print only to console
logging.basicConfig(level=logging.INFO)


@tool
async def search_ticket(
    config: RunnableConfig,
    travel_details: List[TravelDetails],
    passenger_count: PaxCount
) -> List[FlightTicket]:
    """
    Searches for flights based on one-way, return, or multicity travel segments.
    Args:
        travel_details (List[TravelDetails]): 
            A list of travel segments that define the complete journey. 
            
            - For one-way trips: list will contain a single segment.
            - For return trips: list must contain two segments (e.g., outbound and return).
            - For multicity: list must contain  two or more segments in the order they are flown.
            
            Each segment includes:
              - origin (str): Origin airport (IATA code)
              - destination (str): Destination airport (IATA code)
              - travel_date (str): Travel date in YYYY-MM-DD format
              - int_cabin_type (Optional[int]): Cabin class (1–7). Defaults to 5 (Economy)
              Cabin class codes:
                1 - First / Premium
                2 - Business
                3 - Economy All
                4 - Economy Premium
                5 - Economy (default)
                6 - Economy Discounted
                7 - All Classes
        passenger_count (PaxCount): Number of passengers.
    """

    try:
        pax_list = await generate_pax_by_count(**passenger_count)
        dct_variables = await get_ticket_search_variables(travel_details,pax_list)

        # Payload to send in the POST request
        search_payload = {"query": search_by_od_query, "variables": dct_variables}
        
        # Headers
        headers = {
            "Authorization": f'JWT {config.get("configurable").get("token")}',
            "Content-Type": "application/json",
        }

        response = await call_nuflights_api(headers,search_payload)
        
        data = response.json()
    
        lst_shopping = data["data"]["ndcAirShopping"]

        all_offers = []

        for shoping in lst_shopping:
            if not shoping["error"] or not shoping["error"][0]["code"]: # first check if there is no error in the shopping response

                # check offer type is 'FlightOffers' and itineraryList is not empty 
                itinerary_offer = shoping["augmentationPoint"]["shopping"]["offerInstructions"]["itineraryOfferCombinations"]
                
                if itinerary_offer["offerType"] == "FlightOffers" and (
                    itinerary_offer.get("itineraryList") or not itinerary_offer.get("itineraryList") 
                ):

                    offer_combination = await process_offer_combinations(shoping)  # This is only appicable in FlightOffers with itineraryList
                    offer = await process_all_offers(shoping,offer_combination)
                    
                    
                elif itinerary_offer["offerType"] == "CombinationOffers": 

                    offer = await process_all_offers(shoping)

                all_offers.extend(offer)

        formated_offer = await restructure_offers(all_offers)

        return formated_offer
    
    except Exception as e:
        logging.error(f"Error in search_ticket: {e}")
        logging.info(traceback.print_exc())
        return {}


@tool
async def order_ticket(
    config: RunnableConfig, selected_offer: FlightTicket, passengers: List[PaxDeatils]
) -> List[Dict]:
    """
    Order the selected ticket
    
    Args:
        selected_offer (FlightTicket): selected offers details. retrin type ticket may have one or two offer ids 

        passengers (List[PaxDetails]): A list of passenger details required for the booking.
            Each PaxDetails instance should include the following attributes:
            
            - passport_number (str): Passenger's passport number.
            - passport_expiry (str): Passport expiry date in YYYY-MM-DD format.
            - passport_nationality (str): Nationality of the passenger.
            - title (str): Title of the passenger (e.g., Mr, Mrs, Miss).
            - gender (str): Gender of the passenger (e.g., Male, Female, Unspecified).
            - date_of_birth (str): Passenger's date of birth in YYYY-MM-DD format.
            - given_name (str): First name of the passenger (Required).
            - middle_name (str): Middle name of the passenger (Required).
            - sur_name (str): Last name (surname) of the passenger (Required).
            - email (str): Email address of the passenger.
            - phone_country_code (str): Country code of the phone number (e.g., +1, +44).
            - phone (str): Phone number of the passenger.
            - country_code_ISO_3166_1_alpha_2 (str): Intellignetly finds ISO 3166-1 alpha-2 country code for the passenger's residence (e.g., IN for India).
            - frequent_flyer_details (Optional[List[FrequentFlyerInfo]]): List of frequent flyer accounts the passenger is enrolled in. 
                Each item includes:
                - airline_code (str): Airline IATA code (e.g., "QR" for Qatar Airways).
                - frequent_flyer_number (str): Passenger's membership number with that airline.
    """
    try:
    
        today = datetime.today()

        # count adult,child,infant
        adult = child = infant = 0
        
        # set pax details in the order variables.
        pax_details = []
        contact_details = []
        

        lstPaxId = []

        paxList = selected_offer["paxList"]["pax"] # Pax list is same in all selected offer list

        for passenger in passengers:

            dob = datetime.strptime(passenger["date_of_birth"], "%Y-%m-%d")
            age = (today - dob).days // 365
            ptc = ""
            pax_id = ""

            if age >= 12:
                adult += 1
                ptc = "ADT"

            elif 2 <= age < 12:
                child += 1
                ptc = "CHD"

            else:
                infant += 1
                ptc = "INF"

            pax_id = next(
                (p["paxId"] for p in paxList if p["ptc"] == ptc and p["paxId"] not in lstPaxId),
                None
            )

            if pax_id:
                lstPaxId.append(pax_id)

            # Define the middle and last name
            middle_name = passenger.get("middle_name")
            last_name = passenger.get("sur_name", "").upper()

            # Determine the last_name based on the length of the last name
            if len(last_name) < 2:
                # If last name is too short , add the lastname two times
                last_name =  2*last_name

            pax_details.append(await get_pax_details(pax_id,ptc,passenger,middle_name,last_name))

            contact_details.append(await get_contact_details(pax_id,passenger,last_name))
        
        # prepare payload variable for priced offer.
        dct_offer_variables = await get_priced_offer_variable(selected_offer)

        # Payload to send in the POST request
        offer_payload = {"query": offer_price_query, "variables": dct_offer_variables}

        # Headers
        headers = {
            "Authorization": f'JWT {config.get("configurable").get("token")}',
            "Content-Type": "application/json",
        }

        offer_response = await call_nuflights_api(headers,offer_payload)

        priced_offer_data = offer_response.json()

        # check response is valid or not.
        if not priced_offer_data.get("data", {}).get("ndcOfferPrice", {}):
            logging.error(
                f"Error in order_ticket: {priced_offer_data.get('errors', 'No data found')}"
            )
            return [
                {
                    "status": "failed",
                    "message": "Ticket booking failed technical issues",
                }
            ]

        # get the shoping response ID , it uses for further transactions.
        shopping_response_id = priced_offer_data["data"]["ndcOfferPrice"][
            "augmentationPoint"
        ]["provider"]["nfShoppingResponseId"]

        # convert the departure time to datetime object .
        departure_time = datetime.strptime(
            selected_offer["journey"][0]["departureTime"], "%Y-%m-%dT%H:%M:%S"
        )

        # fetch priced offer item, which include all details about the final offer.
        priced_offer_item = priced_offer_data["data"]["ndcOfferPrice"]["response"][
            "pricedOffer"
        ]

        # prepare variable for
        order_variables = await get_ticket_order_variable(selected_offer,
                                                          shopping_response_id,
                                                          departure_time,
                                                          adult,
                                                          child,
                                                          infant,
                                                          passengers[0],
                                                          priced_offer_item,
                                                          pax_details,
                                                          contact_details)
        
        
        order_payload = {"query": order_ticket_query, "variables": order_variables}
        order_response = await call_nuflights_api(headers,order_payload)

        order_data = order_response.json()

        # check response is valid or not.
        if not order_data.get("data", {}).get("ndcOrderCreate", {}):
            logging.error(
                f"Error in order_ticket: {priced_offer_data.get('errors', 'No data found')}"
            )
            return [
                {
                    "status": "failed",
                    "message": "Ticket booking failed technical issues",
                }
            ]

        booking_reference = order_data["data"]["ndcOrderCreate"]["data"]["response"]["order"][0]["orderId"]
        print(f"Booking Reference: {booking_reference}")
        await send_eticket_via_whatsapp(booking_reference, headers, config)
        primary_passenger_name = f"{pax_details[0]["individual"]["givenName"]} {pax_details[0]["individual"]["surname"]}"
        primary_contact_email = contact_details[0]["emailAddress"][0]["emailAddressText"]
        asyncio.create_task(send_eticket_via_email(headers,booking_reference, primary_contact_email, primary_passenger_name))
        

        return [
            {
                "status": "success",
                "message": "Ticket ordered successfully",
                "details": {
                    "Booking Reference": booking_reference.replace("_","/"),
                    "status": "Booked(Hold)",
                    "Additional info": "Requires payment to be completed.",
                    "Send booking confirmationt via email": True
                },
            }
        ]

    except Exception as e:
        logging.error(f"Error in order: {e}")
        logging.info(traceback.print_exc())
        return [
            {
                "status": "failed",
                "message": "Ticket booking failed technical issues",
            }
        ]


@tool
async def get_payment_details(config: RunnableConfig) -> Dict:
    """
    Get payment details for completing the ticket booking.
    
    Returns demo payment information including bank details and payment methods.
    
    Returns:
        Dict: Payment details with bank information and payment options.
    """
    try:
        payment_details = {
            "status": "success",
            "payment_methods": {
                "bank_transfer": {
                    "bank_name": "NuFlights Bank",
                    "account_name": "NuFlights Travel Services",
                    "account_number": "1234567890123456",
                    "ifsc_code": "NUFL0001234",
                    "swift_code": "NUFLINUS",
                    "routing_number": "021000021"
                },
                "upi": {
                    "upi_id": "payments@nuflights.com",
                    "qr_code": "Available on request"
                },
                "card_payment": {
                    "accepted_cards": ["Visa", "MasterCard", "American Express"],
                    "processing_fee": "2.5%"
                }
            },
            "payment_instructions": [
                "Complete payment within 24 hours to confirm booking",
                "Include booking reference in payment description",
                "Payment confirmation will be sent via email and WhatsApp"
            ],
            "support": {
                "phone": "+1-800-NUFLIGHTS",
                "email": "payments@nuflights.com",
                "hours": "24/7 Support Available"
            }
        }
        
        return payment_details
        
    except Exception as e:
        logging.error(f"Error in get_payment_details: {e}")
        return {
            "status": "failed",
            "message": "Unable to retrieve payment details"
        }