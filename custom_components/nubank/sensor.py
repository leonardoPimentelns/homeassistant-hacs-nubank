"""Platform for sensor integration."""
from __future__ import annotations

from datetime import timedelta,datetime
import logging
from matplotlib.font_manager import json_dump
from pynubank import Nubank, MockHttpClient
import pandas as pd
import voluptuous
import json
import locale 
from homeassistant import util
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
locale.setlocale(locale.LC_ALL, '')
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
    nubank = Nubank()
    # nubank = Nubank(MockHttpClient())
    refresh_token = nubank.authenticate_with_cert(config[CONF_CLIENT_ID], config[CONF_CLIENT_SECRET], config[CONF_CLIENT_CERT])
    nubank.authenticate_with_refresh_token(refresh_token, config[CONF_CLIENT_CERT])
    date = pd.to_datetime('today').date() + pd.DateOffset(day=7)
    due_date = date.strftime("%Y-%m-%d")

    add_entities([NuSensor(nubank,due_date)])


class NuSensor(SensorEntity):
    """Representation of a pyNubank sensor."""

    def __init__(self, nubank,due_date):
        """Initialize a new pyNubank sensor."""

        self._attr_name = "Nubank"
        self.nubank = nubank
        self.due_date = due_date
        self.bills = None
        self.total_cumulative = None
        self.total_balance = None
        self.past_balance = None
        self.effective_due_date = None
        self.close_date = None
        self.total_bills = None

       


    @util.Throttle(UPDATE_FREQUENCY)
    def update(self):
        """Update state of sensor."""
        self.account_balance = self.nubank.get_account_balance()
        self._attr_native_value = self.account_balance
        
        self.bills= self.nubank.get_bills()
        count = len(self.bills)-1

        self.transactions = self.nubank.get_card_statements()
        self.bills =[x for x  in self.bills if x['summary']['due_date'] > self.due_date]
        self.bills = pd.json_normalize(self.bills)

        self.total_cumulative = self.bills['summary.total_cumulative'][count]
        self.total_balance = self.bills['summary.total_balance'][count]
        self.past_balance = self.bills['summary.past_balance'][count]
        self.total_cumulative = currency(self.total_cumulative)
        self.total_balance = currency(self.total_balance)
        self.past_balance = currency(self.past_balance)
       
        self.effective_due_date = self.bills['summary.effective_due_date'][count]
        self.effective_due_date = format_date(self.effective_due_date)

        self.close_date = self.bills['summary.close_date'][count]
        self.close_date = format_date(self.close_date) 
        
        self.total_bills = self.bills['summary.total_balance'].sum()
        self.total_bills = currency(self.total_bills)
            


    @property
    def icon(self):
        """Return icon."""
        return "mdi:bank"

    @property
    def extra_state_attributes(self):
        """Return attribute sensor."""
        attributes = {
            "total_cumulative": self.total_cumulative,
            "total_balance": self.total_balance,
            "past_balance": self.past_balance,
            "effective_due_date" :  self.effective_due_date,
            "close_date" :  self.close_date,
            "total_bills" :  self.total_bills
        }
        
        return attributes

def currency(valor):
    valor = locale.currency(valor/100,grouping=True)
    return valor

def format_date(data):
    data = pd.to_datetime(data).strftime("%d %b.")
    return data