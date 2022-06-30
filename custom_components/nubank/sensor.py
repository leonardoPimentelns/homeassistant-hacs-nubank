"""Platform for sensor integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from pynubank import Nubank
import pandas as pd
import voluptuous
from homeassistant import const
from homeassistant.helpers import entity
from homeassistant import util
from homeassistant.helpers import config_validation



REQUIREMENTS = [
    "pynubank==2.17.0",
]

_LOGGER = logging.getLogger(__name__)

CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"
CONF_CLIENT_CERT = "client_cert"
DEFAULT_NAME = 'Nubank'
UPDATE_FREQUENCY = timedelta(minutes=10)
FATURA = 'Fatura'
CONTA = 'Conta'
SENSOR_NAME = '{} {}'
PLATFORM_SCHEMA = config_validation.PLATFORM_SCHEMA.extend(
    {
        voluptuous.Required(CONF_CLIENT_ID): config_validation.string,
        voluptuous.Required(CONF_CLIENT_SECRET): config_validation.string,
        voluptuous.Required(CONF_CLIENT_CERT): config_validation.string,
        voluptuous.Optional(
            const.CONF_NAME,
            default=DEFAULT_NAME
    ):      config_validation.string,

    }
)


def setup_platform(
    hass,
    config,
    add_entities,
    discovery_info
):
    """Set up the pyNubank sensors."""
    nubank = Nubank()
    # nubank = Nubank(MockHttpClient())
    refresh_token = nubank.authenticate_with_cert(config[CONF_CLIENT_ID], config[CONF_CLIENT_SECRET], config[CONF_CLIENT_CERT])
    nubank.authenticate_with_refresh_token(refresh_token, config[CONF_CLIENT_CERT])
    date = pd.to_datetime('today').date() + pd.DateOffset(day=7)
    due_date = date.strftime("%Y-%m-%d")
    name = config.get(const.CONF_NAME)

    add_entities([FaturaSensor(nubank,due_date,name),ContaSensor(nubank,due_date,name)],True)


class NuSensor(entity.Entity):
    """Representation of a pyNubank sensor."""

    def __init__(self, nubank, due_date, name):
        """Initialize a new pyNubank sensor."""
        self._name = name
        self._state = const.STATE_UNKNOWN
        self._attr_name = "Nubank"
        self.due_date = due_date
        self.nubank = nubank
        self.bills = None
        self.status = None
        self.total_cumulative = None
        self.total_balance = None
        self.past_balance = None
        self.effective_due_date = None
        self.close_date = None
        self.total_bills = None
        self.transactions = None
    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        return self._attributes

    @util.Throttle(UPDATE_FREQUENCY)
    def update(self):
        """Fetches new state data for the sensor."""
        raise NotImplementedError

    @property
    def icon(self):
        """Return icon."""
        return "mdi:bank"

    @property
    def state(self):
        """Returns the state of the sensor."""
        return self._state

    @property
    def name(self):
        """Returns the name of the sensor."""
        return SENSOR_NAME.format(self._name, self._name_suffix)

    @property
    def _name_suffix(self):
        """Returns the name suffix of the sensor."""
        raise NotImplementedError


class FaturaSensor(NuSensor):
    """Representation of a pyNubank sensor."""

    @property
    def _name_suffix(self):
        """Returns the name suffix of the sensor."""
        return FATURA

    @util.Throttle(UPDATE_FREQUENCY)
    def update(self):
        self.bills= self.nubank.get_bills()
        self.bills =[x for x  in self.bills if x['summary']['due_date'] > self.due_date]
        self.bills = pd.json_normalize(self.bills)
        count = len(self.bills)-1

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

        self.transactions= self.nubank.get_card_statements()
        groupby_mounth = pd.DataFrame(self.transactions).get(['description', 'title', 'amount', 'time'])
        self.transactions =[x for x  in self.transactions if x['time'] > self.due_date ]
        self.transactions = pd.json_normalize(self.transactions)
        self.transactions = pd.DataFrame(groupby_mounth).groupby(['title']).sum().to_json()

        self._state = self.status
        self._attributes = {}


    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        self._attributes = {
            "total_cumulative": self.total_cumulative,
            "total_balance": self.total_balance,
            "past_balance": self.past_balance,
            "effective_due_date" :  self.effective_due_date,
            "close_date" :  self.close_date,
            "total_bills" :  self.total_bills,
            "transactions": self.transactions
        }
        return  self._attributes

class ContaSensor(NuSensor):
    """Representation of a pyNubank sensor."""

    @property
    def _name_suffix(self):
        """Returns the name suffix of the sensor."""
        return CONTA

    @util.Throttle(UPDATE_FREQUENCY)
    def update(self):

        self._state = self.status
        self._attributes = {}

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        self._attributes = {


        }
        return  self._attributes
def currency(valor):
    valor =  "{:.2f}".format(valor/100)
    return valor
def format_date(data):
    data = pd.to_datetime(data).strftime("%d %b.")
    return data