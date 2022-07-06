"""Platform for sensor integration."""
from __future__ import annotations

from datetime import timedelta
import logging
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
    date = pd.to_datetime('today').date() + pd.offsets.MonthBegin(-1) + pd.DateOffset(day=7)
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
        self.mouth_transactions = None
        self.accont_balance: None

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



        self.status = self.bills['state'][count]

        if self.status == "closed":
            self.total_balance = self.bills['summary.remaining_balance'][count]
        else:
            self.total_balance = self.bills['summary.total_balance'][count]

        self.total_balance = currency(self.total_balance)
        self.total_cumulative = self.bills['summary.total_cumulative'][count]
        self.past_balance = self.bills['summary.past_balance'][count]
        self.total_cumulative = currency(self.total_cumulative)
        self.past_balance = currency(self.past_balance)

        transactions = self.nubank.get_card_statements()
        start_date = pd.to_datetime('today').date() +pd.offsets.MonthBegin(-1) - pd.offsets.Day(+2)
        end_date = pd.to_datetime('today').date() + pd.offsets.MonthBegin() - pd.offsets.Day(+2)

        start_date = start_date.strftime("%Y-%m-%d")
        end_date = end_date.strftime("%Y-%m-%d")



        transactions =[x for x  in transactions if x['time'] > start_date < end_date ]
        # df = pd.DataFrame(columns=['date','description','amount'])
        # for item in transactions:
        #     df.loc[len(df.index)] = [item['time'], item['description'],item['amount']/100]
        # df['date'] = format_date_weekDay(df['date'])

        groupby_mounth = pd.DataFrame(transactions).get(['description', 'title', 'amount', 'time'])

        transactions = pd.DataFrame(groupby_mounth).groupby(['title']).sum()
        transactions['amount'] = transactions['amount']/100
        transactions['percent'] =  transactions['amount'] /transactions['amount'].sum() *100
        transactions['amount'] = transactions['amount'].map('R${}'.format)
        parsed = transactions.to_json(orient="table",index=True,double_precision=2)
        self.mouth_transactions = json.loads(parsed)




        self.effective_due_date = self.bills['summary.effective_due_date'][count]
        self.effective_due_date = format_date(self.effective_due_date)

        self.close_date = self.bills['summary.close_date'][count]
        self.close_date = format_date(self.close_date)

        self.total_bills = self.bills['summary.total_balance'].sum()
        self.total_bills = currency(self.total_bills)

        self._state = self.status
        self._attributes = {}



    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        self._attributes = {
            "total_cumulative": self.total_cumulative,
            "past_balance": self.past_balance,
            "effective_due_date" :  self.effective_due_date,
            "close_date" :  self.close_date,
            "total_bills" :  self.total_bills,
            "total_balance": self.total_balance,
            "mouth_transactions": self.mouth_transactions
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
def currency(valor):
    valor =  "{:.2f}".format(valor/100)
    return valor
def format_date(data):
    data = pd.to_datetime(data).strftime("%d %b.")
    return data
def format_date_weekDay(data):
    data = pd.to_datetime(data).dt.strftime("%a %d %b.")
    return data