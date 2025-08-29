login_query = """
mutation LoginMutation($rq: LoginInput!) {
  login (input: $rq) {
    token
    refreshToken
    refreshExpiresIn
  }
}
"""
search_by_od_query = """
query ndcAirshoppingQuery($rq: AirShoppingRQ!) {
  ndcAirShopping(rq: $rq) {
    payloadAttributes {
      trxId
    }
    augmentationPoint {
      common {
        nfOrderId
        nfSubscriptionId
        isLocalInventorySubscription
      }
      provider {
        nfShoppingResponseId
      }
      shopping {
        offerInstructions {
          itineraryOfferCombinations {
            itineraryType
            offerType
            itineraryList
          }
        }
      }
      agency {
        addServiceFeeToBaseFare
      }
    }
    response {
      offersGroup {
        carrierOffers {
          offer {
            offerItem {
              price {
                totalAmount {
                  curCode
                  cdata
                }
              }
              fareDetail {
                fareComponent {
                  fareBasisCode
                  rbd {
                    rbdCode
                  }
                  cabinType {
                    cabinTypeCode
                    cabinTypeName
                  }
                  priceClassRefId
                  paxSegmentRefId
                }
                paxRefId
                fareIndCode
                filedFareInd
                farePriceType {
                  price {
                    baseAmount {
                      cdata
                      curCode
                    }
                    baseAmountGuaranteeTimeLimitDateTime
                    loyaltyUnitName
                    maskedInd
                    taxSummary {
                      totalTaxAmount {
                        curCode
                        cdata
                      }
                      tax {
                        taxCode
                        taxName
                        approximateInd
                        refundInd
                        collectionInd
                        amount {
                          cdata
                          curCode
                        }
                      }
                    }
                  }
                  farePriceTypeCode
                }
              }
              service {
                paxRefId
                offerServiceAssociation {
                  serviceDefinitionRef {
                    serviceDefinitionRefId
                  }
                  paxJourneyRef {
                    paxJourneyRefId
                  }
                }
                serviceId
              }
              offerItemId
              mandatoryInd
              modificationProhibitedInd
            }
            baggageAssociations {
              baggageAllowanceRefId
              paxRefId
            }
            journeyOverview {
              journeyPriceClass {
                paxJourneyRefId
              }
              priceClassRefId
            }
            ptcOfferParameters {
              pricedPaxNumber
              ptcPricedCode
              ptcRequestedCode
              requestedPaxNumber
            }
            offerId
            ownerCode
            matchAppText
            matchTypeCode
            redemptionInd
            offerExpirationTimeLimitDateTime
            totalPrice {
              totalAmount {
                cdata
                curCode
              }
            }
            validatingCarrierCode
          }
        }
      }
      dataLists {
        baggageAllowanceList {
          baggageAllowance {
            applicablePartyText
            baggageAllowanceId
            descText
            rfisc
            typeCode
            pieceAllowance {
              totalQty
            }
            weightAllowance {
              maximumWeightMeasure
              weightUnitOfMeasurement
            }
            bdc {
              bagRuleCode
              bdcAnalysisResultCode
              bdcReasonText
              carrierDesigCode
              carrierName
            }
          }
        }
        originDestList {
          originDest {
            destCode
            originCode
            originDestId
            paxJourneyRefId
          }
        }
        paxJourneyList {
          paxJourney {
            paxJourneyId
            duration
            paxSegmentRefId
          }
        }
        priceClassList {
          priceClass {
            fareBasisCode
            name
            cabinType {
              cabinTypeCode
              cabinTypeName
            }
            code
            priceClassId
            desc {
              descText
              markupStyleText
              url
            }
          }
        }
        serviceDefinitionList {
          serviceDefinition {
            serviceDefinitionId
            desc {
              descText
              url
            }
          }
        }
        paxList {
          pax {
            paxId
            ptc
          }
        }
        disclosureList {
          disclosure {
            disclosureId
            desc {
              descText
              url
            }
          }
        }
        paxSegmentList {
          paxSegment {
            paxSegmentId
            datedMarketingSegmentRefId
          }
        }
        datedMarketingSegmentList {
          datedMarketingSegment {
            datedMarketingSegmentId
            datedOperatingSegmentRefId
            carrierName
            carrierDesigCode
            arrival {
              aircraftScheduledDateTime
              iataLocationCode
              stationName
              terminalName
            }
            dep {
              aircraftScheduledDateTime
              iataLocationCode
              stationName
              terminalName
            }
            marketingCarrierFlightNumberText
          }
        }
        datedOperatingSegmentList {
          datedOperatingSegment {
            carrierDesigCode
            datedOperatingSegmentId
            duration
            carrierName
          }
        }
      }
    }
    error {
      code
      ownerName
      tagText
      statusText
      descText
      langCode
      errorId
      typeCode
      url
    }
  }
}
"""

offer_price_query = """query ndcOfferPriceQuery(
  $rq: OfferPriceRQ!
) {
  ndcOfferPrice(rq: $rq) {
    payloadAttributes {
      trxId
    }
    augmentationPoint {
      common {
        nfOrderId
        nfSubscriptionId
        isLocalInventorySubscription
      }
      provider {
        nfShoppingResponseId
      }
      agency {
        addServiceFeeToBaseFare
      }
    }
    response {
      otherOffers {
        offer {
          offerId
          ownerCode
          offerExpirationTimeLimitDateTime
          baggageAssociations {
            baggageAllowanceRefId
            paxRefId
          }
          ptcOfferParameters {
            ptcRequestedCode
            requestedPaxNumber
            ptcPricedCode
            pricedPaxNumber
          }
          journeyOverview {
            journeyPriceClass {
              paxJourneyRefId
              priceClassRefId
            }
          }
          offerItem {
            offerItemId
            mandatoryInd
            service {
              serviceId
              paxRefId
              offerServiceAssociation {
                paxJourneyRef {
                  paxJourneyRefId
                }
                serviceDefinitionRef {
                  serviceDefinitionRefId
                }
              }
            }
            fareDetail {
              fareIndCode
              filedFareInd
              paxRefId
              farePriceType {
                farePriceTypeCode
                price {
                  discount {
                    descText
                    discountAmount {
                      cdata
                      curCode
                    }
                  }
                  fee {
                    descText
                    amount {
                      cdata
                      curCode
                    }
                  }
                  totalAmount {
                    cdata
                    curCode
                  }
                  baseAmount {
                    cdata
                    curCode
                  }
                  curConversion {
                    localAmount {
                      curCode
                      cdata
                    }
                    conversionRate {
                      multiplierValue
                    }
                  }
                  taxSummary {
                    approximateInd
                    collectionInd
                    allRefundableInd
                    totalTaxAmount {
                      cdata
                      curCode
                    }
                    tax {
                      taxCode
                      taxName
                      approximateInd
                      refundInd
                      collectionInd
                      amount {
                        cdata
                        curCode
                      }
                    }
                  }
                }
              }
              fareComponent {
                cabinType {
                  cabinTypeCode
                  cabinTypeName
                }
                fareBasisCityPairText
                fareBasisCode
                rbd {
                  rbdCode
                }
                paxSegmentRefId
                priceClassRefId
                price {
                  discount {
                    descText
                    discountAmount {
                      cdata
                      curCode
                    }
                  }
                  fee {
                    descText
                    amount {
                      cdata
                      curCode
                    }
                  }
                  baseAmount {
                    cdata
                    curCode
                  }
                  taxSummary {
                    approximateInd
                    collectionInd
                    allRefundableInd
                    totalTaxAmount {
                      cdata
                      curCode
                    }
                    tax {
                      taxCode
                      taxName
                      approximateInd
                      refundInd
                      collectionInd
                      amount {
                        cdata
                        curCode
                      }
                    }
                  }
                  surcharge {
                    breakdown {
                      amount {
                        cdata
                        curCode
                      }
                      refundInd
                    }
                  }
                }
              }
              accountCode
            }
            modificationProhibitedInd
            price {
              discount {
                descText
                discountAmount {
                  cdata
                  curCode
                }
              }
              fee {
                descText
                amount {
                  cdata
                  curCode
                }
              }
              totalAmount {
                cdata
                curCode
              }
              baseAmount {
                cdata
                curCode
              }
              taxSummary {
                approximateInd
                collectionInd
                allRefundableInd
                totalTaxAmount {
                  cdata
                  curCode
                }
                tax {
                  taxCode
                  taxName
                  approximateInd
                  refundInd
                  collectionInd
                  amount {
                    cdata
                    curCode
                  }
                }
              }
            }
          }
          totalPrice {
            totalAmount {
              curCode
              cdata
            }
            baseAmount {
              curCode
              cdata
            }
            discount {
              descText
              discountAmount {
                cdata
                curCode
              }
            }
            fee {
              descText
              amount {
                cdata
                curCode
              }
            }
          }
        }
      }
      pricedOffer {
        offerId
        ownerCode
        validatingCarrierCode
        matchAppText
        matchTypeCode
        commission {
          amount {
            curCode
            cdata
          }
          commissionCode
          percentage
          percentageAppliedToAmount {
            curCode
            cdata
          }
          taxableInd
        }
        offerItem {
          offerItemId
          mandatoryInd
          service {
            serviceId
            paxRefId
            offerServiceAssociation {
              paxJourneyRef {
                paxJourneyRefId
              }
              serviceDefinitionRef {
                serviceDefinitionRefId
              }
            }
          }
          fareDetail {
            fareIndCode
            filedFareInd
            paxRefId
            farePriceType {
              farePriceTypeCode
              price {
                discount {
                  descText
                  discountAmount {
                    cdata
                    curCode
                  }
                }
                fee {
                  descText
                  amount {
                    cdata
                    curCode
                  }
                }
                totalAmount {
                  cdata
                  curCode
                }
                baseAmount {
                  cdata
                  curCode
                }
                curConversion {
                  localAmount {
                    curCode
                    cdata
                  }
                  conversionRate {
                    multiplierValue
                  }
                }
                taxSummary {
                  approximateInd
                  collectionInd
                  allRefundableInd
                  totalTaxAmount {
                    cdata
                    curCode
                  }
                  tax {
                    taxCode
                    taxName
                    approximateInd
                    refundInd
                    collectionInd
                    amount {
                      cdata
                      curCode
                    }
                  }
                }
              }
            }
            fareComponent {
              cancelRestrictions {
                descText
              }
              changeRestrictions {
                descText
              }
              cabinType {
                cabinTypeCode
                cabinTypeName
              }
              fareBasisCityPairText
              fareBasisCode
              rbd {
                rbdCode
              }
              paxSegmentRefId
              priceClassRefId
              price {
                discount {
                  descText
                  discountAmount {
                    cdata
                    curCode
                  }
                }
                fee {
                  descText
                  amount {
                    cdata
                    curCode
                  }
                }
                baseAmount {
                  cdata
                  curCode
                }
                taxSummary {
                  approximateInd
                  collectionInd
                  allRefundableInd
                  totalTaxAmount {
                    cdata
                    curCode
                  }
                  tax {
                    taxCode
                    taxName
                    approximateInd
                    refundInd
                    collectionInd
                    amount {
                      cdata
                      curCode
                    }
                  }
                }
                surcharge {
                  breakdown {
                    amount {
                      cdata
                      curCode
                    }
                    refundInd
                  }
                }
              }
            }
          }
          modificationProhibitedInd
          price {
            discount {
              descText
              discountAmount {
                cdata
                curCode
              }
            }
            fee {
              descText
              amount {
                cdata
                curCode
              }
            }
            totalAmount {
              cdata
              curCode
            }
            baseAmount {
              cdata
              curCode
            }
            taxSummary {
              approximateInd
              collectionInd
              allRefundableInd
              totalTaxAmount {
                cdata
                curCode
              }
              tax {
                taxCode
                taxName
                approximateInd
                refundInd
                collectionInd
                amount {
                  cdata
                  curCode
                }
              }
            }
          }
        }
        ptcOfferParameters {
          ptcRequestedCode
          requestedPaxNumber
          ptcPricedCode
          pricedPaxNumber
        }
        baggageAssociations {
          baggageAllowanceRefId
          paxRefId
        }
        redemptionInd
        offerExpirationTimeLimitDateTime
        totalPrice {
          totalAmount {
            curCode
            cdata
          }
          baseAmount {
            curCode
            cdata
          }
          discount {
            descText
            discountAmount {
              cdata
              curCode
            }
          }
          fee {
            descText
            amount {
              cdata
              curCode
            }
          }
        }
        journeyOverview {
          journeyPriceClass {
            paxJourneyRefId
            priceClassRefId
          }
        }
      }
      dataLists {
        penaltyList {
          penalty {
            descText
          }
        }
        baggageAllowanceList {
          baggageAllowance {
            applicablePartyText
            baggageAllowanceId
            descText
            rfisc
            typeCode
            pieceAllowance {
              totalQty
            }
            weightAllowance {
              maximumWeightMeasure
              totalMaximumWeightMeasure
              weightUnitOfMeasurement
            }
          }
        }
        serviceDefinitionList {
          serviceDefinition {
            serviceDefinitionId
            desc {
              descText
              url
            }
            name
            ownerCode
            rfic
            rfisc
            serviceCode
            airlineTaxonomy {
              taxonomyCode
              taxonomyFeature {
                valueText
                codesetCode
                codesetNameCode
              }
            }
            serviceDefinitionAssociation {
              baggageAllowanceRef {
                baggageAllowanceRefId
              }
            }
          }
        }
        originDestList {
          originDest {
            destCode
            originCode
            originDestId
            paxJourneyRefId
          }
        }
        paxJourneyList {
          paxJourney {
            paxJourneyId
            duration
            paxSegmentRefId
          }
        }
        priceClassList {
          priceClass {
            fareBasisCode
            name
            cabinType {
              cabinTypeCode
              cabinTypeName
            }
            code
            priceClassId
            desc {
              descText
              markupStyleText
              url
            }
          }
        }
        paxList {
          pax {
            paxId
            ptc
          }
        }
        disclosureList {
          disclosure {
            disclosureId
            desc {
              descText
              url
            }
          }
        }
        paxSegmentList {
          paxSegment {
            paxSegmentId
            datedMarketingSegmentRefId
          }
        }
        datedMarketingSegmentList {
          datedMarketingSegment {
            datedMarketingSegmentId
            datedOperatingSegmentRefId
            carrierDesigCode
            carrierName
            arrival {
              aircraftScheduledDateTime
              iataLocationCode
              stationName
            }
            dep {
              aircraftScheduledDateTime
              iataLocationCode
              stationName
            }
            marketingCarrierFlightNumberText
          }
        }
        datedOperatingSegmentList {
          datedOperatingSegment {
            datedOperatingSegmentId
            carrierDesigCode
            carrierName
            duration
            operatingCarrierFlightNumberText
            datedOperatingLegRefId
          }
        }
        datedOperatingLegList {
          datedOperatingLeg {
            datedOperatingLegId
            carrierAircraftType {
              carrierAircraftTypeName
            }
          }
        }
      }
      paymentFunctions {
        paymentSupportedMethod {
          paymentMethodAddlInfo {
            paymentOtherMethodAddlInfo {
              remark {
                remarkText
              }
            }
          }
        }
      }
    }
    error {
      code
      descText
      errorId
      langCode
      ownerName
      statusText
      tagText
      typeCode
      url
    }
  }
}
"""

offer_price_query = """
query ndcOfferPriceQuery(
  $rq: OfferPriceRQ!
) {
  ndcOfferPrice(rq: $rq) {
    payloadAttributes {
      trxId
    }
    augmentationPoint {
      common {
        nfOrderId
        nfSubscriptionId
        isLocalInventorySubscription
      }
      provider {
        nfShoppingResponseId
      }
      agency {
        addServiceFeeToBaseFare
      }
    }
    response {
      otherOffers {
        offer {
          offerId
          ownerCode
          offerExpirationTimeLimitDateTime
          baggageAssociations {
            baggageAllowanceRefId
            paxRefId
          }
          ptcOfferParameters {
            ptcRequestedCode
            requestedPaxNumber
            ptcPricedCode
            pricedPaxNumber
          }
          journeyOverview {
            journeyPriceClass {
              paxJourneyRefId
              priceClassRefId
            }
          }
          offerItem {
            offerItemId
            mandatoryInd
            service {
              serviceId
              paxRefId
              offerServiceAssociation {
                paxJourneyRef {
                  paxJourneyRefId
                }
                serviceDefinitionRef {
                  serviceDefinitionRefId
                }
              }
            }
            fareDetail {
              fareIndCode
              filedFareInd
              paxRefId
              farePriceType {
                farePriceTypeCode
                price {
                  discount {
                    descText
                    discountAmount {
                      cdata
                      curCode
                    }
                  }
                  fee {
                    descText
                    amount {
                      cdata
                      curCode
                    }
                  }
                  totalAmount {
                    cdata
                    curCode
                  }
                  baseAmount {
                    cdata
                    curCode
                  }
                  curConversion {
                    localAmount {
                      curCode
                      cdata
                    }
                    conversionRate {
                      multiplierValue
                    }
                  }
                  taxSummary {
                    approximateInd
                    collectionInd
                    allRefundableInd
                    totalTaxAmount {
                      cdata
                      curCode
                    }
                    tax {
                      taxCode
                      taxName
                      approximateInd
                      refundInd
                      collectionInd
                      amount {
                        cdata
                        curCode
                      }
                    }
                  }
                }
              }
              fareComponent {
                cabinType {
                  cabinTypeCode
                  cabinTypeName
                }
                fareBasisCityPairText
                fareBasisCode
                rbd {
                  rbdCode
                }
                paxSegmentRefId
                priceClassRefId
                price {
                  discount {
                    descText
                    discountAmount {
                      cdata
                      curCode
                    }
                  }
                  fee {
                    descText
                    amount {
                      cdata
                      curCode
                    }
                  }
                  baseAmount {
                    cdata
                    curCode
                  }
                  taxSummary {
                    approximateInd
                    collectionInd
                    allRefundableInd
                    totalTaxAmount {
                      cdata
                      curCode
                    }
                    tax {
                      taxCode
                      taxName
                      approximateInd
                      refundInd
                      collectionInd
                      amount {
                        cdata
                        curCode
                      }
                    }
                  }
                  surcharge {
                    breakdown {
                      amount {
                        cdata
                        curCode
                      }
                      refundInd
                    }
                  }
                }
              }
              accountCode
            }
            modificationProhibitedInd
            price {
              discount {
                descText
                discountAmount {
                  cdata
                  curCode
                }
              }
              fee {
                descText
                amount {
                  cdata
                  curCode
                }
              }
              totalAmount {
                cdata
                curCode
              }
              baseAmount {
                cdata
                curCode
              }
              taxSummary {
                approximateInd
                collectionInd
                allRefundableInd
                totalTaxAmount {
                  cdata
                  curCode
                }
                tax {
                  taxCode
                  taxName
                  approximateInd
                  refundInd
                  collectionInd
                  amount {
                    cdata
                    curCode
                  }
                }
              }
            }
          }
          totalPrice {
            totalAmount {
              curCode
              cdata
            }
            baseAmount {
              curCode
              cdata
            }
            discount {
              descText
              discountAmount {
                cdata
                curCode
              }
            }
            fee {
              descText
              amount {
                cdata
                curCode
              }
            }
          }
        }
      }
      pricedOffer {
        offerId
        ownerCode
        validatingCarrierCode
        matchAppText
        matchTypeCode
        commission {
          amount {
            curCode
            cdata
          }
          commissionCode
          percentage
          percentageAppliedToAmount {
            curCode
            cdata
          }
          taxableInd
        }
        offerItem {
          offerItemId
          mandatoryInd
          service {
            serviceId
            paxRefId
            offerServiceAssociation {
              paxJourneyRef {
                paxJourneyRefId
              }
              serviceDefinitionRef {
                serviceDefinitionRefId
              }
            }
          }
          fareDetail {
            fareIndCode
            filedFareInd
            paxRefId
            farePriceType {
              farePriceTypeCode
              price {
                discount {
                  descText
                  discountAmount {
                    cdata
                    curCode
                  }
                }
                fee {
                  descText
                  amount {
                    cdata
                    curCode
                  }
                }
                totalAmount {
                  cdata
                  curCode
                }
                baseAmount {
                  cdata
                  curCode
                }
                curConversion {
                  localAmount {
                    curCode
                    cdata
                  }
                  conversionRate {
                    multiplierValue
                  }
                }
                taxSummary {
                  approximateInd
                  collectionInd
                  allRefundableInd
                  totalTaxAmount {
                    cdata
                    curCode
                  }
                  tax {
                    taxCode
                    taxName
                    approximateInd
                    refundInd
                    collectionInd
                    amount {
                      cdata
                      curCode
                    }
                  }
                }
              }
            }
            fareComponent {
              cancelRestrictions {
                descText
              }
              changeRestrictions {
                descText
              }
              cabinType {
                cabinTypeCode
                cabinTypeName
              }
              fareBasisCityPairText
              fareBasisCode
              rbd {
                rbdCode
              }
              paxSegmentRefId
              priceClassRefId
              price {
                discount {
                  descText
                  discountAmount {
                    cdata
                    curCode
                  }
                }
                fee {
                  descText
                  amount {
                    cdata
                    curCode
                  }
                }
                baseAmount {
                  cdata
                  curCode
                }
                taxSummary {
                  approximateInd
                  collectionInd
                  allRefundableInd
                  totalTaxAmount {
                    cdata
                    curCode
                  }
                  tax {
                    taxCode
                    taxName
                    approximateInd
                    refundInd
                    collectionInd
                    amount {
                      cdata
                      curCode
                    }
                  }
                }
                surcharge {
                  breakdown {
                    amount {
                      cdata
                      curCode
                    }
                    refundInd
                  }
                }
              }
            }
          }
          modificationProhibitedInd
          price {
            discount {
              descText
              discountAmount {
                cdata
                curCode
              }
            }
            fee {
              descText
              amount {
                cdata
                curCode
              }
            }
            totalAmount {
              cdata
              curCode
            }
            baseAmount {
              cdata
              curCode
            }
            taxSummary {
              approximateInd
              collectionInd
              allRefundableInd
              totalTaxAmount {
                cdata
                curCode
              }
              tax {
                taxCode
                taxName
                approximateInd
                refundInd
                collectionInd
                amount {
                  cdata
                  curCode
                }
              }
            }
          }
        }
        ptcOfferParameters {
          ptcRequestedCode
          requestedPaxNumber
          ptcPricedCode
          pricedPaxNumber
        }
        baggageAssociations {
          baggageAllowanceRefId
          paxRefId
        }
        redemptionInd
        offerExpirationTimeLimitDateTime
        totalPrice {
          totalAmount {
            curCode
            cdata
          }
          baseAmount {
            curCode
            cdata
          }
          discount {
            descText
            discountAmount {
              cdata
              curCode
            }
          }
          fee {
            descText
            amount {
              cdata
              curCode
            }
          }
        }
        journeyOverview {
          journeyPriceClass {
            paxJourneyRefId
            priceClassRefId
          }
        }
      }
      dataLists {
        penaltyList {
          penalty {
            descText
          }
        }
        baggageAllowanceList {
          baggageAllowance {
            applicablePartyText
            baggageAllowanceId
            descText
            rfisc
            typeCode
            pieceAllowance {
              totalQty
            }
            weightAllowance {
              maximumWeightMeasure
              totalMaximumWeightMeasure
              weightUnitOfMeasurement
            }
          }
        }
        serviceDefinitionList {
          serviceDefinition {
            serviceDefinitionId
            desc {
              descText
              url
            }
            name
            ownerCode
            rfic
            rfisc
            serviceCode
            airlineTaxonomy {
              taxonomyCode
              taxonomyFeature {
                valueText
                codesetCode
                codesetNameCode
              }
            }
            serviceDefinitionAssociation {
              baggageAllowanceRef {
                baggageAllowanceRefId
              }
            }
          }
        }
        originDestList {
          originDest {
            destCode
            originCode
            originDestId
            paxJourneyRefId
          }
        }
        paxJourneyList {
          paxJourney {
            paxJourneyId
            duration
            paxSegmentRefId
          }
        }
        priceClassList {
          priceClass {
            fareBasisCode
            name
            cabinType {
              cabinTypeCode
              cabinTypeName
            }
            code
            priceClassId
            desc {
              descText
              markupStyleText
              url
            }
          }
        }
        paxList {
          pax {
            paxId
            ptc
          }
        }
        disclosureList {
          disclosure {
            disclosureId
            desc {
              descText
              url
            }
          }
        }
        paxSegmentList {
          paxSegment {
            paxSegmentId
            datedMarketingSegmentRefId
          }
        }
        datedMarketingSegmentList {
          datedMarketingSegment {
            datedMarketingSegmentId
            datedOperatingSegmentRefId
            carrierDesigCode
            carrierName
            arrival {
              aircraftScheduledDateTime
              iataLocationCode
              stationName
            }
            dep {
              aircraftScheduledDateTime
              iataLocationCode
              stationName
            }
            marketingCarrierFlightNumberText
          }
        }
        datedOperatingSegmentList {
          datedOperatingSegment {
            datedOperatingSegmentId
            carrierDesigCode
            carrierName
            duration
            operatingCarrierFlightNumberText
            datedOperatingLegRefId
          }
        }
        datedOperatingLegList {
          datedOperatingLeg {
            datedOperatingLegId
            carrierAircraftType {
              carrierAircraftTypeName
            }
          }
        }
      }
      paymentFunctions {
        paymentSupportedMethod {
          paymentMethodAddlInfo {
            paymentOtherMethodAddlInfo {
              remark {
                remarkText
              }
            }
          }
        }
      }
    }
    error {
      code
      descText
      errorId
      langCode
      ownerName
      statusText
      tagText
      typeCode
      url
    }
  }
}
"""
order_ticket_query = """mutation ndcOrderCreateMutation(
  $rq: OrderCreateRQ!
) {
  ndcOrderCreate(rq: $rq) {
    data {
      augmentationPoint {
        common {
          nfOrderId
          nfSubscriptionId
        }
        provider {
          nfShoppingResponseId
        }
        agency {
          addServiceFeeToBaseFare
        }
      }
      payloadAttributes {
        trxId
      }
      response {
        dataLists {
          baggageAllowanceList {
            baggageAllowance {
              applicablePartyText
              baggageAllowanceId
              descText
              rfisc
              typeCode
              weightAllowance {
                maximumWeightMeasure
              }
              bdc {
                bagRuleCode
                bdcAnalysisResultCode
                bdcReasonText
                carrierDesigCode
                carrierName
              }
            }
          }
          contactInfoList {
            contactInfo {
              contactInfoId
              phone {
                phoneNumber
              }
              emailAddress {
                emailAddressText
                contactTypeText
              }
            }
          }
          serviceDefinitionList {
            serviceDefinition {
              serviceDefinitionId
              name
              ownerCode
              rfic
              rfisc
              serviceCode
              airlineTaxonomy {
                descText
                taxonomyCode
              }
              serviceDefinitionAssociation {
                baggageAllowanceRef {
                  baggageAllowanceRefId
                }
              }
            }
          }
          originDestList {
            originDest {
              destCode
              originCode
              originDestId
              paxJourneyRefId
            }
          }
          paxJourneyList {
            paxJourney {
              paxJourneyId
              duration
              paxSegmentRefId
            }
          }
          priceClassList {
            priceClass {
              fareBasisCode
              name
              cabinType {
                cabinTypeCode
                cabinTypeName
              }
              code
              priceClassId
              desc {
                descText
                markupStyleText
                url
              }
            }
          }
          paxList {
            pax {
              paxId
              ptc
              paxRefId
              contactInfoRefId
              birthdate
              individual {
                individualId
                genderCode
                birthdate
                titleName
                givenName
                surname
                middleName
              }
              identityDoc {
                identityDocTypeCode
                identityDocId
                issuingCountryCode
                citizenshipCountryCode
                expiryDate
                givenName
                middleName
                surname
                genderCode
                birthdate
              }
              profileConsentInd
            }
          }
          disclosureList {
            disclosure {
              disclosureId
              desc {
                descText
                url
              }
            }
          }
          paxSegmentList {
            paxSegment {
              paxSegmentId
              datedMarketingSegmentRefId
            }
          }
          datedMarketingSegmentList {
            datedMarketingSegment {
              datedMarketingSegmentId
              datedOperatingSegmentRefId
              carrierDesigCode
              arrival {
                aircraftScheduledDateTime
                iataLocationCode
                stationName
              }
              dep {
                aircraftScheduledDateTime
                iataLocationCode
                stationName
              }
              marketingCarrierFlightNumberText
            }
          }
          datedOperatingSegmentList {
            datedOperatingSegment {
              datedOperatingSegmentId
              carrierDesigCode
              duration
              operatingCarrierFlightNumberText
            }
          }
        }
        order {
          orderId
          ownerCode
          orderItem {
            orderItemId
            creationDateTime
            paymentTimeLimitDateTime
            bilateralTimeLimit {
              name
              timeLimitDateTime
            }
            price {
              totalAmount {
                cdata
                curCode
              }
              baseAmount {
                cdata
                curCode
              }
              taxSummary {
                approximateInd
                collectionInd
                allRefundableInd
                totalTaxAmount {
                  cdata
                  curCode
                }
                tax {
                  taxCode
                  taxName
                  approximateInd
                  refundInd
                  collectionInd
                  amount {
                    cdata
                    curCode
                  }
                }
              }
            }
            fareDetail {
              fareIndCode
              filedFareInd
              paxRefId
              farePriceType {
                farePriceTypeCode
                price {
                  totalAmount {
                    cdata
                    curCode
                  }
                  baseAmount {
                    cdata
                    curCode
                  }
                  curConversion {
                    localAmount {
                      curCode
                      cdata
                    }
                    conversionRate {
                      multiplierValue
                    }
                  }
                  taxSummary {
                    approximateInd
                    collectionInd
                    allRefundableInd
                    totalTaxAmount {
                      cdata
                      curCode
                    }
                    tax {
                      taxCode
                      taxName
                      approximateInd
                      refundInd
                      collectionInd
                      amount {
                        cdata
                        curCode
                      }
                    }
                  }
                }
              }
              fareComponent {
                cabinType {
                  cabinTypeCode
                  cabinTypeName
                }
                fareBasisCityPairText
                fareBasisCode
                rbd {
                  rbdCode
                }
                paxSegmentRefId
                priceClassRefId
                price {
                  baseAmount {
                    cdata
                    curCode
                  }
                  taxSummary {
                    approximateInd
                    collectionInd
                    allRefundableInd
                    totalTaxAmount {
                      cdata
                      curCode
                    }
                    tax {
                      taxCode
                      taxName
                      approximateInd
                      refundInd
                      collectionInd
                      amount {
                        cdata
                        curCode
                      }
                    }
                  }
                  surcharge {
                    breakdown {
                      amount {
                        cdata
                        curCode
                      }
                      refundInd
                    }
                  }
                }
                fareRule {
                  ruleCode
                  remark {
                    remarkText
                  }
                }
              }
            }
            service {
              serviceId
              paxRefId
              statusCode
              bookingRef {
                bookingId
              }
            }
          }
          totalPrice {
            totalAmount {
              cdata
              curCode
            }
          }
        }
        ticketDocInfo {
          paxRefId
          referencedOrder {
            orderId
            ownerCode
          }
          servicingAgency {
            typeCode
            agencyId
            iataNumber
          }
          originalIssueInfo {
            issueDate
            issueTime
            ticketNumber
            issuingCarrier {
              airlineDesigCode
            }
          }
          bookletQty
          ticket {
            ticketDocTypeCode
            ticketNumber
            reportingTypeCode
            primaryDocInd
            coupon {
              couponNumber
              couponStatusCode
              currentCouponFlightInfoRef {
                currentAirlinePaxSegmentRef {
                  paxSegmentRefId
                }
              }
              consumedAtIssuanceInd
              nonRefundableInd
              nonInterlineableInd
              nonCommissionableInd
              nonReissuableNonExchInd
            }
            taxOnEmdInd
            exchReissueInd
            presentCreditCardInd
          }
          fareDetail {
            farePriceType {
              farePriceTypeCode
              price {
                baseAmount {
                  cdata
                  curCode
                }
                taxSummary {
                  totalTaxAmount {
                    cdata
                    curCode
                  }
                  approximateInd
                  collectionInd
                  allRefundableInd
                  tax {
                    taxCode
                    taxName
                    approximateInd
                    refundInd
                    collectionInd
                  }
                }
                surcharge {
                  breakdown {
                    amount {
                      cdata
                      curCode
                    }
                    refundInd
                  }
                }
                totalAmount {
                  cdata
                  curCode
                }
              }
            }
          }
        }
      }
      paymentFunctions {
        paymentProcessingSummary {
          paymentId
          amount {
            cdata
            curCode
          }
          paymentRefId
          paymentStatusCode
          verificationInd
        }
        orderAssociation {
          orderRefId
          orderItemRefId
        }
        paymentSupportedMethod {
          paymentMethodAddlInfo {
            paymentOtherMethodAddlInfo {
              remark {
                remarkText
              }
            }
          }
        }
      }
      error {
        code
        descText
        errorId
        langCode
        ownerName
        statusText
        tagText
        typeCode
        url
      }
    }
  }
}
"""
download_ticket_query = """
mutation ItineraryApiDownloadPdfMutation(
  $input: GenerateItineraryPdfInput!
) {
  generateItineraryPdf(input: $input) {
    url
  }
}

"""
send_ticket_via_email_query = """
mutation ItineraryApiEmailPdfMutation(
  $input: SendEmailItineraryPdfInput!
) {
  sendItineraryPdf(input: $input) {
    success
  }
}

"""