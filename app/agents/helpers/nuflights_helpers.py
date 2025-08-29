import httpx
import json
from datetime import datetime
import logging
from typing import Optional, List, TypedDict
from app.agents.utils.general_methods import get_media_id, send_whatsapp_document
from app.agents.helpers.nuflights_queries import (
    download_ticket_query,
    send_ticket_via_email_query,
)

# Configure logging to print only to console
logging.basicConfig(level=logging.INFO)


class PaxCount(TypedDict):
    """
    Passenger class to define passenger details.
    """

    adult: int
    child: int
    infant: Optional[int] = 0

class TravelDetails(TypedDict):
    """
    Travel details class to define travel details.
    """
    origin: str  # Origin airport IATA code
    destination: str  # Destination airport IATA code
    travel_date: str  # Travel date in YYYY-MM-DD format
    int_cabin_type: Optional[int] = 5  # Cabin type code (1-7)

class OfferItem(TypedDict):
    """
    Offer item class to define offer item details.
    """
    offerItemRefId: str  # offeritem id
    paxRefId: List[str]  # pax reference id


class FlightSegment(TypedDict):
    """
    Represents flight and journey details.
    """
    offerRefId : str
    flightNumber: str
    departureAirport: str
    departureTime: str
    arrivalAirport: str
    arrivalTime: str
    duration: Optional[str]
    MarketingSegmentCarrierName: Optional[str]
    OperatingSegmentCarrierName: Optional[str]
    aircraftIATACode: Optional[str]


class Pax(TypedDict):
    paxId: str
    ptc: str

class PaxList(TypedDict):
    """
    A container for a list of passengers.
    """
    pax: List[Pax]


class offerMetaData(TypedDict):
    """
    Offer details.
    """
    offerId: str
    totalPrice: str
    description: str
    currency: str
    ownerCode: str
    offerItem: List[OfferItem]
    baggageAllowances: Optional[dict] 

class FlightTicket(TypedDict):
    """
    Represents the flight ticket offer details.
    """
    journey: List[FlightSegment]
    offerMetaData: List[offerMetaData]
    priceClass: str
    cabinTypeCode: int
    subscriptionId: str
    shoppingResponseId: str
    transactionID: str  # Required, UUID used for tracking the booking process
    paxList: PaxList

class FrequentFlyerInfo(TypedDict):
    """
    Frequent flyer information.
    """
    airline_code: str      # e.g., "QR" for Qatar Airways
    frequent_flyer_number: str  # e.g., "QR123456789"

class PaxDeatils(TypedDict):
    """
    Passenger details class to define passenger details.
    """

    passport_number: str  # Passport number of the passenger
    passport_expiry: str  # Passport expiry date in YYYY-MM-DD format
    passport_nationality: str  # Nationality of the passenger
    title: str  # Passenger title (e.g., Mr, Mrs, Miss
    gender: str  # Gender of the passenger (e.g., Male, Female, Unspecified)
    date_of_birth: str  # Date of birth in YYYY-MM-DD format
    given_name: str  # First name of the passenger
    middle_name: Optional[str]  # Middle name of the passenger
    sur_name: str  # Last name of the passenger
    email: str  # Email address of the passenger
    phone_contry_code: str  # Country code for the phone number (e.g., +1, +44)
    phone: str  # Phone number of Passenger.
    counry_code_ISO_3166_1_alpha_2: (
        str  # Country code of the passenger's residence (e.g., IN for India)
    )
    frequent_flyer_details : Optional[List[FrequentFlyerInfo]] = None


# hasmap table , used to find  flight class by cabin type ID.
dct_flight_class = {
    1: "First / Premium",
    2: "Business",
    3: "Economy All",
    4: "Economy Premium",
    5: "Economy",
    6: "Economy Discounted",
    7: "All Classes",
}


async def generate_pax_by_count(adult=0, child=0, infant=0):
    """
    generate pax list format by adult,child,infant counts.
    """
    pax_list = []
    pax_counter = 1
    adult_ids = []

    # Add adults
    for _ in range(adult):
        pax_id = f"T{pax_counter}"
        pax_list.append({"ptc": "ADT", "paxId": pax_id})
        adult_ids.append(pax_id)
        pax_counter += 1

    # Add children
    for _ in range(child):
        pax_id = f"T{pax_counter}"
        pax_list.append({"ptc": "CHD", "paxId": pax_id})
        pax_counter += 1

    # Add infants (linked to adults)
    for i in range(infant):
        if i < len(adult_ids):
            pax_list.append({"ptc": "INF", "paxId": f"{adult_ids[i]}.1"})
        else:
            raise ValueError(
                "Each infant must be assigned to an adult. Not enough adults."
            )

    return pax_list

async def process_offer_combinations(shopping):
    
    itineraries = shopping["augmentationPoint"]["shopping"]["offerInstructions"]["itineraryOfferCombinations"]["itineraryList"]
    
    offer_map = {}
    for itinerary in itineraries:
        journey_offers = itinerary["journeyOffersList"]
        od1_offer = next((o for o in journey_offers if o["originDestId"] == "OD1"), None)
        od2_offer = next((o for o in journey_offers if o["originDestId"] == "OD2"), None)

        if od1_offer and od2_offer:
            od1_id = od1_offer["offerId"]
            od2_id = od2_offer["offerId"]

            if od1_id not in offer_map:
                offer_map[od1_id] = []
            if od2_id not in offer_map[od1_id]:
                offer_map[od1_id].append(od2_id)

    #  Limit to 3 OD1 offerIds only
    selected_od1 = list(offer_map.keys())[:3]

    # Limit to 3 OD2s per OD1
    limited_offer_map = {
        od1_id: offer_map[od1_id][:3]
        for od1_id in selected_od1
    }

    with open("offer_combination_output.json", "w") as f:
        json.dump(limited_offer_map, f, indent=4)

    return limited_offer_map

async def process_all_offers(shopping, dct_offer_combination=None):
    try:
        """
        Formats the ticket offer JSON to be more readable and well-structured .
        """
        all_offers = []


        data = shopping["response"]
        subscription_id = shopping["augmentationPoint"]["common"]["nfSubscriptionId"]

        shoping_response_id = shopping.get("augmentationPoint", {}).get("provider", {}).get("nfShoppingResponseId") if shopping.get("augmentationPoint", {}).get("provider", {}) else None
        transaction_id = shopping.get("payloadAttributes", {}).get("trxId")

        # Extract the main components
        offers_group = data["offersGroup"]
        data_lists = data["dataLists"]

        # Create lookup dictionaries for faster access
        baggage_lookup = {
            bag["baggageAllowanceId"]: bag
            for bag in data_lists["baggageAllowanceList"]["baggageAllowance"]
        }
        price_class_lookup = {
            pc["priceClassId"]: pc for pc in data_lists["priceClassList"]["priceClass"]
        }
        pax_segment_lookup = {
            seg["paxSegmentId"]: seg
            for seg in data_lists["paxSegmentList"]["paxSegment"]
        }
        marketing_segment_lookup = {
            seg["datedMarketingSegmentId"]: seg
            for seg in data_lists["datedMarketingSegmentList"]["datedMarketingSegment"]
        }

        operating_segment_lookup = {
            seg["datedOperatingSegmentId"]: seg
            for seg in data_lists["datedOperatingSegmentList"]["datedOperatingSegment"]
        }
        operating_leg_lookup = {} # Initialize in case datedOperatingLegList is missing
        if "datedOperatingLegList" in data_lists:
            operating_leg_lookup = {
                leg["datedOperatingLegId"]: leg
                for leg in data_lists["datedOperatingLegList"]["datedOperatingLeg"]
            }
        pax_journey_lookup = {
            journey["paxJourneyId"]: journey
            for journey in data_lists["paxJourneyList"]["paxJourney"]
        }
        pax_list_lookup = data_lists["paxList"]


        # Initialize the list to hold offers
        offers_to_process = offers_group["carrierOffers"][0]["offer"]

        # ✅ If no combination map provided, limit to first 3 offers (beacause flight offers with iternary list is already limited into 3)
        if dct_offer_combination is None:
            offers_to_process = offers_to_process[:3]

            
        # Process each offer in the carrier's offers
        for offer in offers_to_process:
            description = ""
            travel_class = ""
            price_class_ref_id = offer["offerItem"][0]["fareDetail"][0]["fareComponent"][0]["priceClassRefId"]
            cabin_code = offer["offerItem"][0]["fareDetail"][0]["fareComponent"][0]["cabinType"]["cabinTypeCode"]

            price_class_details = price_class_lookup.get(price_class_ref_id)
            if price_class_details:
                travel_class = price_class_details.get("name", "")
                desc_items = price_class_details.get("desc")
                if desc_items and isinstance(desc_items, list):
                    desc_list = [
                        item.get("descText", "")
                        for item in desc_items
                        if "descText" in item
                    ]
                    description = "\n".join(filter(None, desc_list))


            # Selecting offerItemId and its corresponding paxRefIds
            offer_items = offer["offerItem"]
            dct_offer_item=[]
            for offer_item in offer_items:

                services = offer_item["service"]
                lst_pax_ref_id = []

                for service in services:

                    for pax_ref_id in service["paxRefId"]:
                        if pax_ref_id not in lst_pax_ref_id:
                            lst_pax_ref_id.append(pax_ref_id)

                dct_offer_item.append({
                    "offerItemRefId": offer_item["offerItemId"],
                    "paxRefId" : lst_pax_ref_id
                })


            # Process baggage associations
            baggage_dict = {}

            for baggage_assoc in offer.get("baggageAssociations") or []:
                for baggage_ref in baggage_assoc["baggageAllowanceRefId"]:
                    baggage_data = baggage_lookup.get(baggage_ref)
                    if baggage_data:
                        baggage_dict = {
                            "weight_limit": (
                                baggage_data["weightAllowance"][0][
                                    "maximumWeightMeasure"
                                ]
                                if baggage_data.get("weightAllowance")
                                else None
                            ),
                            "weight_unit": (
                                baggage_data["weightAllowance"][0][
                                    "weightUnitOfMeasurement"
                                ]
                                if baggage_data.get("weightAllowance")
                                else None
                            )
                        }


            # Process flight segments from journey overview
            lstFlightPath = []
            if "journeyOverview" in offer:
                for journey_price_class in offer["journeyOverview"].get(
                    "journeyPriceClass", []
                ):
                    journey_id = journey_price_class["paxJourneyRefId"]
                    journey_data = pax_journey_lookup.get(journey_id)

                    if journey_data:
                        for segment_ref in journey_data["paxSegmentRefId"]:
                            segment_data = pax_segment_lookup.get(segment_ref)

                            if segment_data:
                                marketing_segment_id = segment_data[
                                    "datedMarketingSegmentRefId"
                                ]

                                marketing_segment = marketing_segment_lookup.get(
                                    marketing_segment_id
                                )


                                if marketing_segment:
                                    operating_segment_id = marketing_segment[
                                        "datedOperatingSegmentRefId"
                                    ]
                                    operating_segment = operating_segment_lookup.get(
                                        operating_segment_id
                                    )

                                    operating_leg = None
                                    if operating_segment and operating_segment.get(
                                        "datedOperatingLegRefId"
                                    ):
                                        operating_leg_id = operating_segment[
                                            "datedOperatingLegRefId"
                                        ][0]
                                        operating_leg = operating_leg_lookup.get(
                                            operating_leg_id
                                        )

                                    lstFlightPath.append({
                                        "offerRefId": offer["offerId"], # Add offerRefId to each flight segment
                                        "flightNumber": marketing_segment["marketingCarrierFlightNumberText"],
                                        "departureAirport": marketing_segment["dep"]["iataLocationCode"],
                                        "departureTime": marketing_segment["dep"]["aircraftScheduledDateTime"],
                                        "arrivalAirport": marketing_segment["arrival"]["iataLocationCode"],
                                        "arrivalTime": marketing_segment["arrival"]["aircraftScheduledDateTime"],
                                        "duration": segment_data.get("segmentDuration"),
                                        "MarketingSegmentCarrierName": marketing_segment["carrierName"],
                                        "OperatingSegmentCarrierName": operating_segment.get("carrierName","") if operating_segment else None,
                                        "aircraftIATACode": (
                                            (operating_leg.get("iataAircraftType") or {}).get("iataAircraftTypeCode")
                                            if operating_leg else None
                                        )
                                    })
            dct_offer_details = {
                "journey":lstFlightPath,
                "ownerCode": offer["ownerCode"],
                "offerId": offer["offerId"],
                "offerExpiry": offer["offerExpirationTimeLimitDateTime"],
                "totalPrice": offer["totalPrice"]["totalAmount"]["cdata"],
                "currency": offer["totalPrice"]["totalAmount"]["curCode"],
                "priceClass": travel_class,
                "description": description,
                "offerItem": dct_offer_item,
                "baggageAllowances": baggage_dict,
                "cabinTypeCode": cabin_code,
                "subscriptionId": subscription_id,
                "shoppingResponseId": shoping_response_id,
                "transactionID": transaction_id,
                "paxList": pax_list_lookup,

            }

            if dct_offer_combination: # flight offers with iternary list

                # Filter strictly to only OD1 in keys or OD2 in values
                should_include = False

                if dct_offer_combination:
                    # OD1 case
                    if offer["offerId"] in dct_offer_combination:
                        dct_offer_details["connectingOfferIds"] = dct_offer_combination[offer["offerId"]]
                        should_include = True

                    # OD2 case
                    else:
                        for od2_list in dct_offer_combination.values():
                            if offer["offerId"] in od2_list:
                                dct_offer_details["connectingOfferIds"] = []
                                should_include = True
                                break

                if should_include:
                    all_offers.append(dct_offer_details)
            else:
                all_offers.append(dct_offer_details)


        return all_offers

    except Exception:
        import traceback
        traceback.print_exc()
        return []
    
    
async def restructure_offers(flat_offers):
    
    restructured_data = []
    offer_lookup = {offer["offerId"]: offer for offer in flat_offers}
    processed_od2_ids = set() # Keep track of OD2 offers that have been paired

    for offer in flat_offers:
        offer_id = offer["offerId"]

        # Common metadata for the top level of the combined offer
        common_metadata = {
            "priceClass": offer.get("priceClass"),
            "cabinTypeCode": offer.get("cabinTypeCode"),
            "subscriptionId": offer.get("subscriptionId"),
            "shoppingResponseId": offer.get("shoppingResponseId"),
            "transactionID": offer.get("transactionID"),
            "paxList": offer.get("paxList")
        }

        # Case 1: This is a main OD1 offer with connecting offers
        if "connectingOfferIds" in offer and offer["connectingOfferIds"]:
            # Iterate through each possible connecting offer (OD2)
            for connecting_offer_id in offer["connectingOfferIds"]:
                if connecting_offer_id in offer_lookup and connecting_offer_id not in processed_od2_ids:
                    connecting_offer = offer_lookup[connecting_offer_id]

                    combined_journey = []
                    offer_metadata = []

                    # Add the OD1 offer's journey and metadata
                    combined_journey.extend(offer["journey"])
                    offer_metadata.append({
                        "offerId": offer["offerId"],
                        "totalPrice": offer["totalPrice"],
                        "description": offer["description"],
                        "currency": offer["currency"],
                        "ownerCode": offer["ownerCode"],
                        "offerItem": offer["offerItem"],
                        "baggageAllowances": offer["baggageAllowances"]
                    })

                    # Add the paired OD2 offer's journey and metadata
                    combined_journey.extend(connecting_offer["journey"])
                    offer_metadata.append({
                        "offerId": connecting_offer["offerId"],
                        "totalPrice": connecting_offer.get("totalPrice", ""),
                        "description": connecting_offer["description"],
                        "currency": connecting_offer["currency"],
                        "ownerCode": connecting_offer["ownerCode"],
                        "offerItem": connecting_offer["offerItem"],
                        "baggageAllowances": connecting_offer["baggageAllowances"]
                    })

                    restructured_data.append({
                        "journey": combined_journey,
                        "offerMetaData": offer_metadata,
                        **common_metadata
                    })
                    processed_od2_ids.add(connecting_offer_id) # Mark OD2 as processed

        # Case 2: This is a direct offer or an OD2 offer that was not part of any combination (unlikely if logic is correct)
        # We only add it if it hasn't been processed as part of an OD1-OD2 combination
        elif offer_id not in processed_od2_ids: # Ensure it's not an OD2 already handled
            # For direct offers, the journey and metadata are just its own
            restructured_data.append({
                "journey": offer["journey"],
                "offerMetaData": [{
                    "offerId": offer["offerId"],
                    "totalPrice": offer["totalPrice"],
                    "description": offer["description"],
                    "currency": offer["currency"],
                    "ownerCode": offer["ownerCode"],
                    "offerItem": offer["offerItem"],
                    "baggageAllowances": offer["baggageAllowances"]
                }],
                **common_metadata
            })

    return restructured_data

async def get_ticket_search_variables(
    travel_details, pax_list
):
    lst_origin_dest_criteria = []
    
    for index,details in enumerate(travel_details,start=1):
        lst_origin_dest_criteria.append({
                                "originDestId": f"OD{index}",
                                "originDepCriteria": {
                                    "date": details['travel_date'],
                                    "iataLocationCode": details['origin'],
                                },
                                "destArrivalCriteria": {
                                    "iataLocationCode": details['destination']
                                },
                                "cabinType": [
                                    {
                                        "cabinTypeCode": details.get("int_cabin_type", 5),
                                        "prefLevel": {"prefLevelCode": "Preferred"},
                                    }
                                ],
                            })
        
    return {
        "rq": {
            "distributionChain": {
                "distributionChainLink": [
                    {
                        "ordinal": "1",
                        "orgRole": "Seller",
                        "participatingOrg": {"orgId": ""},
                    }
                ]
            },
            "payloadAttributes": {},
            "request": {
                "flightRequest": {
                    "flightRequestOriginDestinationsCriteria": {
                        "originDestCriteria": lst_origin_dest_criteria
                    }
                },
                "paxList": {"pax": pax_list},
            },
        }
    }


async def get_pax_details(pax_id, ptc, passenger, middle_name, last_name):

    lst_loyalty_prgm_accts=[]

    loyality_deatils = passenger.get("frequent_flyer_details")

    if loyality_deatils:
        for loyality in  loyality_deatils:
            lst_loyalty_prgm_accts.append(
                {
                        "loyaltyProgram": {
                        "carrier": {
                            "airlineDesigCode": loyality.get("airline_code")
                            }
                        },
                        "accountNumber": loyality.get("frequent_flyer_number")
                }
            )

    dct_pax_details = {
        "paxId": pax_id,
        "ptc": ptc,
        "individual": {
            "birthdate": passenger["date_of_birth"],
            "genderCode": {"MALE": "M", "FEMALE": "F"}.get(
                passenger.get("gender", "").upper(), "X"
            ),
            "titleName": passenger["title"].upper(),
            "givenName": [passenger["given_name"].upper()],
            "surname": last_name,
            "individualId": pax_id,
        },
        "identityDoc": [
            {
                "identityDocTypeCode": "PT",
                "identityDocId": passenger["passport_number"],
                "issuingCountryCode": passenger["counry_code_ISO_3166_1_alpha_2"],
                "residenceCountryCode": passenger["counry_code_ISO_3166_1_alpha_2"],
                "surname": last_name,
                "expiryDate": passenger["passport_expiry"],
            }
        ],
        "langUsage": [{"langCode": "EN"}],
        "contactInfoRefId": f"ContactInfo-{pax_id}",
    }

    if lst_loyalty_prgm_accts:
        dct_pax_details["loyaltyProgramAccount"] = lst_loyalty_prgm_accts

    if middle_name:
        dct_pax_details["individual"]["middleName"] = middle_name

    return dct_pax_details


async def get_contact_details(pax_id, passenger, last_name):
    return {
        "contactInfoId": f"ContactInfo-{pax_id}",
        "emailAddress": [
            {
                "emailAddressText": passenger["email"].upper(),
                "contactTypeText": "Home",
            }
        ],
        "individual": {
            "givenName": [passenger["given_name"].upper()],
            "surname": last_name,
        },
        "individualRefId": pax_id ,
        "phone": [
            {
                "contactTypeText": "Home",
                "countryDialingCode": passenger["phone_contry_code"].strip("+"),
                "areaCodeNumber": passenger["phone"][:3],
                "phoneNumber": passenger["phone"][3:],
                "extensionNumber": passenger["phone"][:3],
            }
        ],
    }


async def get_priced_offer_variable(selected_offer):
    return {
        "rq": {
            "augmentationPoint": {
                "common": {"nfSubscriptionId": selected_offer["subscriptionId"]},
                "provider": {
                    "nfShoppingResponseId": selected_offer["shoppingResponseId"]
                },
            },
            "distributionChain": {
                "distributionChainLink": [
                    {
                        "ordinal": "1",
                        "orgRole": "Seller",
                        "participatingOrg": {"orgId": ""},
                    }
                ]
            },
            "request": {
                "pricedOffer": {
                    "selectedOfferList": {
                        "selectedOffer": [
                            {
                                "offerRefId": offer["offerId"],
                                "ownerCode": offer["ownerCode"],
                                "selectedOfferItem": offer["offerItem"],
                                
                            } for offer in selected_offer["offerMetaData"]
                        ]
                    }
                },
                "dataLists": {
                    "paxList": selected_offer["paxList"],
                },
            },
            "payloadAttributes": {"trxId": selected_offer["transactionID"]},
        }
    }


async def get_ticket_order_variable(
    selected_offer,
    shopping_response_id,
    departure_time,
    adult,
    child,
    infant,
    primary_passenger,
    priced_offer_item,
    pax_details,
    contact_details,
):
    origin_dest_criteria = []

    for idx, journey in enumerate(selected_offer["journey"], start=1):
        
        origin_dest_criteria.append({
            "originDestId": f"OD{idx}",
            "originDepCriteria": {
                "date": datetime.strptime(journey["departureTime"], "%Y-%m-%dT%H:%M:%S").strftime("%Y-%m-%d"),
                "iataLocationCode": journey["departureAirport"],
            },
            "destArrivalCriteria": {
                "iataLocationCode": journey["arrivalAirport"]
            },
            "cabinType": [
                {
                    "cabinTypeCode": selected_offer["cabinTypeCode"],
                    "prefLevel": {"prefLevelCode": "Preferred"},
                }
            ],
        })
    
    lst_selected_offers = []
    
    # Selecting offeritemRefid with its corresponding pax ids 
    for offerItem in priced_offer_item["offerItem"]:
        pax_ref_ids = []
        for fareitem in offerItem["fareDetail"]: 
            for pax_ref_id in fareitem["paxRefId"]:
                if pax_ref_id not in  pax_ref_ids:
                    pax_ref_ids.append(pax_ref_id)

        lst_selected_offers.append({
                "offerItemRefId": offerItem["offerItemId"],
                "paxRefId": pax_ref_ids,
            })
                                    
        
    return {
        "rq": {
            "distributionChain": {
                "distributionChainLink": [
                    {
                        "ordinal": "1",
                        "orgRole": "Seller",
                        "participatingOrg": {"orgId": "65211193"},
                    }
                ]
            },
            "augmentationPoint": {
                "common": {"nfSubscriptionId": selected_offer["subscriptionId"]},
                "provider": {"nfShoppingResponseId": shopping_response_id},
                "savedOriginalSearch": {
                    "request": {
                        "departure": selected_offer["journey"][0]["departureAirport"],
                        "arrival": selected_offer["journey"][0]["arrivalAirport"],
                        "departureDate": departure_time.strftime(
                            "%Y-%m-%dT%H:%M:%S.000Z"
                        ),
                        "adults": adult,
                        "child": child,
                        "infant": infant,
                        "daysdifference": 0,
                        "flightClass": dct_flight_class.get(
                            selected_offer["cabinTypeCode"],"Economy"
                        ),
                        "returnDate": departure_time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                        "tripCount": 0,
                        "originDestCriteria": origin_dest_criteria,
                    }
                },
            },
            "payloadAttributes": {"trxId": selected_offer["transactionID"]},
            "pos": {
                "country": {
                    "countryCode": primary_passenger["counry_code_ISO_3166_1_alpha_2"]
                }
            },
            "request": {
                "createOrder": {
                    "acceptSelectedQuotedOfferList": {
                        "selectedPricedOffer": [
                            {
                                "offerRefId": priced_offer_item["offerId"],
                                "ownerCode": priced_offer_item["ownerCode"],
                                "selectedOfferItem": lst_selected_offers,
                            }
                        ]
                    }
                },
                "dataLists": {
                    "paxList": {"pax": pax_details},
                    "contactInfoList": {"contactInfo": contact_details},
                },
            },
        }
    }


async def send_eticket_via_whatsapp(booking_reference, headers, config):
    try:

        # GraphQL payload
        payload = {
            "query": download_ticket_query,
            "variables": {"input": {"ownerOrderId": booking_reference}},
        }
        # Request PDF URL
        response = await call_nuflights_api(headers, payload)

        response.raise_for_status()
        pdf_url = (
            response.json().get("data", {}).get("generateItineraryPdf", {}).get("url")
        )

        if not pdf_url:
            logging.error("Failed to retrieve PDF URL.")
            return

        # Download PDF
        async with httpx.AsyncClient() as client:
            response = await client.get(pdf_url)
            pdf_content = response.content

        # Get WhatsApp config
        whatsapp_config = config.get("configurable", {})
        whatsapp_body = whatsapp_config.get("whatsapp_body")
        whatsapp_token = whatsapp_config.get("whatsapp_token")

        # Upload media and get media ID
        media_id = await get_media_id(whatsapp_body, pdf_content, whatsapp_token)

        # Prepare and send WhatsApp message
        booking_reference = booking_reference.replace("_", "/")
        caption = f"📄 Your flight booking confirmation - {booking_reference}"
        await send_whatsapp_document(
            whatsapp_body,
            media_id,
            whatsapp_token,
            f"Booking_{booking_reference}",
            caption,
        )

    except Exception as e:
        logging.error(f"Unexpected error: {e}")


async def send_eticket_via_email(
    headers, booking_reference, email, primary_passenger_name
):
    # GraphQL payload
    payload = {
        "query": send_ticket_via_email_query,
        "variables": {
            "input": {
                "ownerOrderId": booking_reference,
                "passengerId": "",
                "toEmail": [email],
                "ccEmail": [],
                "primaryPassengerName": primary_passenger_name,
            }
        },
    }

    try:
        # Request PDF URL
        response = await call_nuflights_api(headers, payload)
        response.raise_for_status()

        return

    except Exception as e:
        logging.error(f"Unexpected error: {e}")


async def call_nuflights_api(headers, payload):
    try:
        # Request PDF URL
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.staging.llc.nuflights.com/core/graphql",
                headers=headers,
                json=payload,
                timeout=240,
            )
        response.raise_for_status()
        return response
        
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
