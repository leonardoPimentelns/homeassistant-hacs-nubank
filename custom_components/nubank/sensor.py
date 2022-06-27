"""Platform for sensor integration."""
from __future__ import annotations

from datetime import timedelta,datetime
import logging
from matplotlib.font_manager import json_dump
from pynubank import Nubank, MockHttpClient
import pandas as pd
import voluptuous
import json
from homeassistant import util
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
TODAY = str(datetime.now())

REQUIREMENTS = [
    "pynubank==2.17.0",
    "requests==2.27.1",
    "qrcode==7.3.1",
    "pyOpenSSL==22.0.0",
    "colorama==0.4.3",
    "requests-pkcs12==1.13",
]

_LOGGER = logging.getLogger(__name__)

CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"
CONF_CLIENT_CERT = "client_cert"
UPDATE_FREQUENCY = timedelta(minutes=10)

PLATFORM_SCHEMA = config_validation.PLATFORM_SCHEMA.extend(
    {
        voluptuous.Required(CONF_CLIENT_ID): config_validation.string,
        voluptuous.Required(CONF_CLIENT_SECRET): config_validation.string,
        voluptuous.Required(CONF_CLIENT_CERT): config_validation.string,
    }
)


def setup_platform(
    hass,
    config,
    add_entities: AddEntitiesCallback,
    discovery_info
):
    """Set up the pyNubank sensors."""
    # nubank = Nubank()
    nubank = Nubank(MockHttpClient())
    refresh_token = nubank.authenticate_with_cert(config[CONF_CLIENT_ID], config[CONF_CLIENT_SECRET], config[CONF_CLIENT_CERT])
    nubank.authenticate_with_refresh_token(refresh_token, config[CONF_CLIENT_CERT])

    add_entities([NuSensor(nubank)])


class NuSensor(SensorEntity):
    """Representation of a pyNubank sensor."""

    def __init__(self, nubank):
        """Initialize a new pyNubank sensor."""

        self._attr_name = "Nubank"
        self.bills = None
        self.account_balance = None
        self.transactions = None
        self.group_title = None
        self.nubank = nubank
        self.purchases = None

    @util.Throttle(UPDATE_FREQUENCY)
    def update(self):
        """Update state of sensor."""

        card_statements = self.nubank.get_card_statements()
        self.account_balance = self.nubank.get_account_balance()
        self.bills = sum(t["amount"] for t in card_statements)
        self._attr_native_value = self.account_balance
        self.transactions = self.nubank.get_card_statements()
        self.purchases = pd.DataFrame(self.transactions)

        start_date = first_day_of_month(TODAY)
        end_date = last_day_of_month(TODAY)

        self.purchases['time'] = pd.to_datetime(self.purchases['time'])
        self.purchases[(self.purchases['time'] > start_date)  & (self.purchases['time'] <= end_date)]
        self.purchases = pd.DataFrame(self.transactions).to_json()




        print(self.purchases)
        print(start_date)
        print(end_date)

    @property
    def icon(self):
        """Return icon."""
        return "mdi:bank"

    @property
    def extra_state_attributes(self):
        """Return attribute sensor."""
        attributes = {
            "Bills": self.bills,
            "Account Balance": self.account_balance,
            # "Transactions": self.transactions,
            "Purchases" :  self.purchases
        }
        return attributes
def last_day_of_month(date: str) -> str:
    return str(pd.Timestamp(date) + pd.offsets.MonthBegin(1) - pd.offsets.Day(+2))

def first_day_of_month(date: str) -> str:
    return str(pd.Timestamp(date) + pd.offsets.MonthBegin(-1) - pd.offsets.Day())
