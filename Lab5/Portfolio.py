import itertools
import json

from tabulate import tabulate


class Portfolio:
    def __init__(self, apiClasses, configFile):
        self.__apiClasses = apiClasses
        self.__configFile = configFile
        self.__baseCurrency = None
        self.__resources = None
        self.__resourcesSigns = None
        self.__apis = None
        self.__arbitrages = None
        self.__saleProfits = None
        self.__percent = None

    def configure(self, configFile=None):
        if not configFile:
            configFile = self.__configFile

        try:
            with open(configFile, "r") as config_file:
                data = json.load(config_file)

            self.__baseCurrency = data['base_currency']
            self.__resources = data['resources']

        except FileNotFoundError:
            print("File '{}' not found.".format(self.__configFile))
        except KeyError as ke:
            print("File error - {} not found. Please reformat file.".format(ke))

        if not self.__baseCurrency or not self.__resources:
            exit()

        print("base_currency: {}\nresources: {}".format(self.__baseCurrency, self.__resources))

        # TODO czy '__resourcesSigns' jako pole? czy jest gdzies jeszcze potrzebne?
        self.__resourcesSigns = list(self.__resources.keys())

        print("\nResources signs: {}".format(self.__resourcesSigns))

        self.__apis = []

        for apiClass in self.__apiClasses:
            self.__apis.append(apiClass(self.__resourcesSigns))

        # for api in self.__apis:
        #     print("\nAPI '{}': {}".format(api, api.markets))
        #
        #     for resourceSign in self.__resourcesSigns:
        #         print("- {}: {}".format(resourceSign + "-" + self.__baseCurrency,
        #                                 api.getOrderbook((resourceSign, self.__baseCurrency))['bids']))

        self.__percent = float(input("% you want to calculate: "))

        # TODO zmiana EUR na USD - nazwa, ceny; arbitraz ma dotyczyc woluminu z zasobow oraz nalezy dodac cene wplaty i wyplaty z gieldy - przerobic funkcje liczaca arbitraz

    def calculate(self):
        self.__calculateSaleProfits()
        self.__calculateArbitrages()

    def __calculateSaleProfits(self):
        test_sale_profits = [("BTC", 0.0003, 30000.03, 125225.01, 21312.3, 2131213.24, 1232.12, "BB"),
                             ("LTC", 0.01, 200.03, 225.01, 2.3, 13.24, 0.12, "BITT"),
                             ("BTC", 0.0003, 30000.03, 125225.01, 21312.3, 2131213.24, 1232.12, "BB"),
                             ("BTC", 0.0003, 30000.03, 125225.01, 21312.3, 2131213.24, 1232.12, "BB"),
                             ("BTC", 0.0003, 30000.03, 125225.01, 21312.3, 2131213.24, 1232.12, "BB")]

        self.__saleProfits = test_sale_profits

    def __calculateArbitrages(self):
        self.__arbitrages = set()

        apis_pairs = itertools.permutations(self.__apis, 2)

        for api1, api2 in apis_pairs:
            markets = Portfolio.__findCommonMarkets(api1, api2)

            for market in markets:
                arbitrage = Portfolio.__calculateArbitrage(api1, api2, market)

                if arbitrage[1] > 0:
                    self.__arbitrages.add(arbitrage)

        self.__arbitrages = sorted(self.__arbitrages, key=lambda x: float(x[1]), reverse=True)

    @staticmethod
    def __findCommonMarkets(api1, api2):
        markets1 = api1.markets
        markets2 = api2.markets

        return markets1 & markets2

    @staticmethod
    def __calculateArbitrage(api1, api2, market):
        asks = api1.getOrderbook(market)["asks"]
        bids = api2.getOrderbook(market)["bids"]

        volumes_to_trade = Portfolio.__calculateVolumesToTrade(asks, bids)

        asks = volumes_to_trade["asks"]
        bids = volumes_to_trade["bids"]

        asks_taker_fee = api1.fees["taker"]
        bids_taker_fee = api2.fees["taker"]

        purchase_cost = 0
        purchased_volume = 0

        for (volume, price) in asks:
            purchase_cost += price * volume
            purchased_volume += volume * (1 - asks_taker_fee)

        purchased_volume -= api1.fees["transfer"][market[1]]

        sale_profit = 0

        for (volume, price) in bids:
            if purchased_volume - volume <= 0:
                sale_profit += price * purchased_volume * (1 - bids_taker_fee)
                break

            purchased_volume -= volume
            sale_profit += price * volume * (1 - bids_taker_fee)

        difference = sale_profit - purchase_cost

        return market, difference, (api1, api2)

    @staticmethod
    def __calculateVolumesToTrade(asks, bids):
        result = {"asks": [], "bids": []}

        if not asks or not bids:
            return result

        best_ask = asks[0]
        best_bid = bids[0]

        if best_ask[1] >= best_bid[1]:
            max_volume = min(best_ask[0], best_bid[0])
            result["asks"].append((max_volume, best_ask[1]))
            result["bids"].append((max_volume, best_bid[1]))

            return result

        for i in range(len(asks) - 1, -1, -1):
            ask = asks[i]
            if ask[1] < best_bid[1]:
                bids_temp = []

                for bid in bids:
                    if ask[1] < bid[1]:
                        bids_temp.append(bid)
                    else:
                        break
                bids = bids_temp
                asks = asks[:i + 1]
                break

        bids_volume = 0
        asks_volume = 0

        for bid in bids:
            bids_volume += bid[0]

        for ask in asks:
            asks_volume += ask[0]

        max_volume = min(bids_volume, asks_volume)

        bids_volume = 0
        asks_volume = 0

        for bid in bids:
            if bids_volume + bid[0] >= max_volume:
                result["bids"].append((max_volume - bids_volume, bid[1]))
                break

            bids_volume += bid[0]
            result["bids"].append(bid)

        for ask in asks:
            if asks_volume + ask[0] >= max_volume:
                result["asks"].append((max_volume - asks_volume, ask[1]))
                break

            asks_volume += ask[0]
            result["asks"].append(ask)

        return result

    def __createTable(self):
        table = [["NAZWA", "ILOSC", "CENA", "WARTOSC", "WARTOSC {}%".format(self.__percent), "WARTOSC NETTO",
                  "WARTOSC {}% NETTO".format(self.__percent), "GIELDA", "   ", "ARBITRAZ"]]

        sale_profits_size = len(self.__saleProfits)
        arbitrages_size = len(self.__arbitrages)

        rows_number = max(sale_profits_size, arbitrages_size)

        volume_sum = 0
        price_sum = 0
        value_sum = 0
        percent_value_sum = 0
        netto_value_sum = 0
        netto_percent_value_sum = 0

        for i in range(rows_number):
            resource_name = None
            volume = None
            price = None
            value = None
            percent_value = None
            netto_value = None
            netto_percent_value = None
            exchange = None
            arbitrage_market = (None, None)
            arbitrage_difference = None
            arbitrage_api1 = None
            arbitrage_api2 = None
            arbitrage = None

            if i < sale_profits_size:
                resource_name, volume, price, value, percent_value, netto_value, netto_percent_value, exchange \
                    = self.__saleProfits[i]

                volume_sum += volume
                price_sum += price
                value_sum += value
                percent_value_sum += percent_value
                netto_value_sum += netto_value
                netto_percent_value_sum += netto_percent_value

            if i < arbitrages_size:
                arbitrage_market, arbitrage_difference, (arbitrage_api1, arbitrage_api2) = self.__arbitrages[i]
                arbitrage = "{}-{}, {}-{}, +{:.8f}{}".format(arbitrage_api1.sign,
                                                             arbitrage_api2.sign,
                                                             arbitrage_market[0],
                                                             arbitrage_market[1],
                                                             arbitrage_difference,
                                                             arbitrage_market[0])

            if value:
                table.append([resource_name,
                              "{0:.8f}".format(volume),
                              "{0:.2f}".format(price),
                              "{0:.2f}".format(value),
                              "{0:.2f}".format(percent_value),
                              "{0:.2f}".format(netto_value),
                              "{0:.2f}".format(netto_percent_value),
                              exchange,
                              "   ",
                              arbitrage])
            else:
                table.append([resource_name,
                              None,
                              None,
                              None,
                              None,
                              None,
                              None,
                              exchange,
                              "   ",
                              arbitrage])

        table.append([" ", " ", " ", " ", " ", " ", " ", " ", " ", " "])

        table.append(["SUMA",
                      "{0:.8f}".format(volume_sum),
                      "{0:.2f}".format(price_sum),
                      "{0:.2f}".format(value_sum),
                      "{0:.2f}".format(percent_value_sum),
                      "{0:.2f}".format(netto_value_sum),
                      "{0:.2f}".format(netto_percent_value_sum),
                      None,
                      "   ",
                      None])

        return table

    def printTable(self):
        table = self.__createTable()
        print(tabulate(table, headers='firstrow', tablefmt='fancy_grid',
                       colalign=["center", "right", "right", "right", "right", "right", "right", "center", "center",
                                 "left"]))
        print()

        # print("\n# ARBITRAGES")
        # for arbitrage in self.__arbitrages:
        #     print(
        #         "{} | {} | {}".format(arbitrage[1], arbitrage[0], (str(arbitrage[2][0]) + "-" + str(arbitrage[2][1]))))
