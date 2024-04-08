from decimal import Decimal

import requests
from custom_exceptions import NoPositionsError, InvalidTokens, InvalidSolanaAddress, DecimalsNotFoundError, NO_LIQUDITY

from common import PriceInfo, TokenOverview
from helpers import is_solana_address


class Config:
    BIRD_EYE_TOKEN = "451846c7a9bc440d933652aba468b9e9"


class BirdEyeClient:
    """
    Handler class to assist with all calls to BirdEye API
    """

    @property
    def _headers(self):
        return {
            "accept": "application/json",
            "x-chain": "solana",
            "X-API-KEY": Config.BIRD_EYE_TOKEN,
        }

    def _make_api_call(self, method: str, query_url: str, *args, **kwargs) -> requests.Response:
        match method.upper():
            case "GET":
                query_method = requests.get
            case "POST":
                query_method = requests.post
            case _:
                raise ValueError(f'Unrecognised method "{method}" passed for query - {query_url}')
        resp = query_method(query_url, *args, headers=self._headers, **kwargs)
        return resp

    def fetch_prices(self, token_addresses: list[str]) -> dict[str, PriceInfo[Decimal, Decimal]]:
        """
        For a list of tokens fetches their prices
        via multi-price API ensuring each token has a price

        Args:
            token_addresses (list[str]): A list of tokens for which to fetch prices

        Returns:
           dict[str, dict[str, PriceInfo[Decimal, Decimal]]: Mapping of token to a named tuple PriceInfo with price and liquidity

        Raises:
            NoPositionsError: Raise if no tokens are provided
            InvalidToken: Raised if the API call was unsuccessful
        """
        if not token_addresses:
            raise NoPositionsError()
        url = f"https://public-api.birdeye.so/public/multi_price?include_liquidity=true&list_address={'%2C'.join(token_addresses)}"
        response = self._make_api_call("GET", url)
        if response.status_code == 200:
            data = response.json()
            prices = {}
            invalid_tokens = []
            for token_address, token_data in data["data"].items():
                if "value" in token_data and "liquidity" in token_data:
                    price_info = PriceInfo(Decimal(token_data["value"]), Decimal(token_data["liquidity"]))
                    prices[token_address] = price_info
                else:
                    invalid_tokens.append(token_address)
            if invalid_tokens:
                raise InvalidTokens(invalid_tokens)
            return prices
        else:
            raise InvalidTokens()

    def fetch_token_overview(self, address: str) -> TokenOverview:
        """
        For a token fetches their overview
        via multi-price API ensuring each token has a price

        Args:
            address (str): A token address for which to fetch overview

        Returns:
            dict[str, float | str]: Overview with a lot of token information I don't understand

        Raises:
            InvalidSolanaAddress: Raise if invalid solana address is passed
            InvalidToken: Raised if the API call was unsuccessful
            DecimalsNotFoundError: Raised if the API response does not contain decimals
            InvalidTokens: Raised if the API call was unsuccessful
        """
        if not is_solana_address(address):
            raise InvalidSolanaAddress(address)
        url = f"https://public-api.birdeye.so/public/multi_price?include_liquidity=true&include_decimals=true&list_address={address}"
        response = self._make_api_call("GET", url)
        if response.status_code == 200:
            data = response.json()["data"]
            token_data = data.get(address, {})
            if not token_data:
                raise InvalidTokens(address)

            price = Decimal(token_data.get("value", 0))
            symbol = token_data.get("symbol", "")
            decimals = int(token_data.get("decimals", 0))
            last_trade_unix_time = int(token_data.get("lastTradeUnixTime", 0))
            liquidity = Decimal(token_data.get("liquidity", 0))
            supply = Decimal(token_data.get("supply", 0))

            if decimals == 0:
                raise DecimalsNotFoundError()
            if liquidity == 0:
                raise ValueError(NO_LIQUDITY)
            return TokenOverview(price, symbol, decimals, last_trade_unix_time, liquidity, supply)
        else:
            raise InvalidTokens()
