from pynubank import Nubank
import pandas as pd
import matplotlib
from datetime import date,datetime
from pynubank import Nubank, MockHttpClient
import json
nu = Nubank()
# nu = Nubank(MockHttpClient())
# # # Essa linha funciona porque não estamos chamando o servidor do Nubank ;

refresh_token = nu.authenticate_with_cert('09958780640', 'acbp0103', 'cert.p12')
nu.authenticate_with_refresh_token(refresh_token, 'cert.p12')


card_statements = nu.get_card_statements()

notification = nu.get_card_feed()
df = pd.DataFrame(notification).get(['description'])
# df.last_valid_index()
print(df)


# print(transactions)
