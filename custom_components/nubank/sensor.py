"""Platform for sensor integration."""
from __future__ import annotations

from datetime import timedelta,datetime,date
import logging
from matplotlib.font_manager import json_dump
from pynubank import Nubank
import random
import decimal
import voluptuous
import json
from homeassistant import const
from homeassistant.helpers import entity
from homeassistant import util
from homeassistant.helpers import config_validation



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
   
   

    refresh_token = nubank.authenticate_with_cert(config[CONF_CLIENT_ID], config[CONF_CLIENT_SECRET], config[CONF_CLIENT_CERT])
    nubank.authenticate_with_refresh_token(refresh_token, config[CONF_CLIENT_CERT])

    today = date.today()
    first_day_next_month = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
    due_date = first_day_next_month + timedelta(days=6)


    due_date_str = due_date.strftime("%Y-%m-%d")
    

    add_entities([FaturaSensor(nubank,due_date_str),ContaSensor(nubank,due_date_str)],True)


class NuSensor(entity.Entity):
    """Representation of a pyNubank sensor."""

    def __init__(self, nubank, due_date_str,):
        """Initialize a new pyNubank sensor."""
        
        self._state = None
        self._attr_name = "Nubank"
        self.due_date_str = due_date_str
        self.nubank = nubank
        self.status = None
        self.total_cumulative = None
        self.credit_card_available = None
        self.total_balance = None
        self.total_bills = None
        self.mouth_transactions = None
        self.accont_balance= None
        self.get_bill_details=None

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




class FaturaSensor(NuSensor):
    """Representation of a pyNubank sensor."""

    @util.Throttle(UPDATE_FREQUENCY)
    def update(self):
        bills = self.nubank.get_bills()
        data = self.nubank.get_credit_card_balance()

        self.credit_card_available = decimal.Decimal(str(data["available"] / 100))
        filtered_bills = [x for x in bills if x['summary']['due_date'] == self.due_date_str]
        bill_details = self.nubank.get_bill_details(filtered_bills[0])
        bill_details['bill']['summary']['total_balance'] = bill_details['bill']['summary']['total_balance'] / 100
        bill_details['bill']['summary']['total_balance'] = "R${0}".format(bill_details['bill']['summary']['total_balance'])

        for bill in bill_details['bill']['line_items']:
            bill['amount'] = bill['amount'] / 100
            bill['amount'] = "R${0}".format(bill['amount'])
            bill['post_date'] = datetime.strptime(bill['post_date'], '%Y-%m-%d').strftime('%a %d %b.')
            if 'index' in bill and bill['index'] > 0:
                bill['parcelas'] = f"{bill['index'] + 1}/{bill['charges']}"

        self.mouth_transactions = bill_details

        for bill in filtered_bills:
            bill_details = self.nubank.get_bill_details(bill)
            line_items = bill_details['bill']['line_items']
            total_amount =0
            attributes = []

            category_totals = {}
            for item in line_items:
                title = item['title']
                amount = item['amount'] 
                category = item['category']
                
                if amount < 0:
                    continue
                
                if category not in category_totals:
                    category_totals[category] = 0
                category_totals[category] += amount
                
                attributes.append({"title": title, "amount": amount, "category": category})
            
            bill_total_amount = round(sum(item['amount'] for item in line_items if item['amount'] > 0) / 100, 2)
            total_amount += bill_total_amount
            bills_details = {"total": f"R${bill_total_amount}","available":self.credit_card_available, "categories": []}
            
            for category, total in category_totals.items():
                if total > 0:
                    percentage = round((total / bill_total_amount) * 100, 2)/100
                    amount_string = round(total / 100, 2)
                    category_details = {"name": category, "total": amount_string, "percentage":f"{round(percentage,2)}%","color": format("#{:06x}".format(random.randint(0, 0xFFFFFF)))}
                    bills_details["categories"].append(category_details)
                    bills_details["categories"].sort(key=lambda x: x['total'],reverse=True) 
                   

                    self.bills_mounth = bills_details



        self._state =  total_amount



    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        self._attributes = {
            "total_cumulative": self.bills_mounth,
            "transactions": self.mouth_transactions

        }
        return  self._attributes


class ContaSensor(NuSensor):
    """Representation of a pyNubank sensor."""

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
# def format_date(data):
#     data = pd.to_datetime(data).strftime("%d %b.")
#     return data
# def format_date_weekDay(data):
#     data = pd.to_datetime(data).dt.strftime("%a %d %b.")
#     return data
