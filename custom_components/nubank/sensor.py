"""Platform for sensor integration."""
from __future__ import annotations

from datetime import timedelta,datetime
import logging
from matplotlib.font_manager import json_dump
from pynubank import Nubank

import pandas as pd
import voluptuous
import json
from homeassistant import const
from homeassistant.helpers import entity
from homeassistant import util
from homeassistant.helpers import config_validation



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
DEFAULT_NAME = 'Nubank'
UPDATE_FREQUENCY = timedelta(minutes=1)
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
    date = pd.to_datetime('today').date() + pd.offsets.MonthBegin() + pd.DateOffset(day=7)

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
        self.total_bills = None
        self.mouth_transactions = None
        self.accont_balance= None
        self.mouth_transactions_summary=None

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
        self.bills =[x for x  in self.bills if x['summary']['due_date'] == self.due_date ]

        for bills_details  in self.bills:
            df_bills = self.nubank.get_bill_details(bills_details)
            df_bills = pd.DataFrame(df_bills['bill']['line_items']).get(['amount','category'])
            df_bills = pd.DataFrame(df_bills).groupby(['category']).sum()
            df_bills = df_bills.loc[df_bills['amount'] > 0]
            df_bills['amount'] = df_bills['amount']/100
            df_bills['percent'] =  df_bills['amount'] /df_bills['amount'].sum() *100
            df_bills['amount'] = df_bills['amount'].map('R${}'.format)
            parsed = df_bills.to_json(orient="table",index=True,double_precision=2)
            self.bills_mounth = json.loads(parsed)

        for bills_details  in self.bills:
            gb = self.nubank.get_bill_details(bills_details)
            transactions = pd.DataFrame(gb['bill']['line_items'])
            transactions['amount'] = transactions['amount']/100
            transactions['amount'] = transactions['amount'].map('R${}'.format)
            transactions['post_date'] = pd.to_datetime(transactions['post_date'])
            transactions['post_date'] = transactions['post_date'].apply(lambda x: x.strftime('%d %b.'))
            parsed = transactions.to_json(orient="table",index=True,double_precision=2)
            self.mouth_transactions = json.loads(parsed)
      



        self._state = ''
        self._attributes = {}



    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        self._attributes = {
            "total_cumulative": self.bills_mounth,
            "summary": self.bills,
            "transactions": self.mouth_transactions
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
        self.accont_balance = self.nubank.get_account_balance()
        self._state = self.accont_balance
        self._attributes = {}

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        self._attributes = {


        }
        return  self._attributes
# def currency(valor):
#     valor =  "{:.2f}".format(valor/100)
#     return valor
def format_date(s: pd.Series):
    s = pd.to_datetime.strptime(s,"%d %b.")
    return s
# def format_date_weekDay(data):
#     data = pd.to_datetime(data).dt.strftime("%a %d %b.")
#     return data