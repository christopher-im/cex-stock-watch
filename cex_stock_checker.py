#!python3

import sys
from configparser import ConfigParser
import argparse
import os
from time import sleep
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import logging
import pickle

import requests

CHECK_URL = "https://wss2.cex.uk.webuy.io/v3/boxes/{}/detail"

EMAIL_HTML = r"""<html>
    <head></head>
    <body>
    <h1 style="font-size: 40px">CEX stock check</h1>
    <p>
        <span style="font-size: 25px">In Stock:</span>
        <ul style="list-style-type:square">
            <span style="font-size: 20px">{}</span>
        </ul>
        <span style="font-size: 25px">Out of Stock:</span>
        <ul style="list-style-type:square">
            <span style="font-size: 20px">{}</span>
        </ul><br>

        <span style="font-size: 25px">Items currently in the checklist:</span>
        <ul style="list-style-type:square">
            <span style="font-size: 20px">{}</span>
        </ul>
    </p>
    </body>
</html>"""

def check_stock():
    in_stock = []
    out_of_stock = []
    email_trigger = False
    for item in config['general']['items'].split(','):
        item_in_stock, item_name = check_item_in_stock(item)
        if item_in_stock:
            logger.info('Item %s in stock', item_name)
            in_stock.append(item)
        else:
            logger.info('Item %s not in stock', item_name)
            out_of_stock.append(item)

    if config['general']['persist'] or args.persist:
        if os.path.isfile('items.dat'):
            with open('items.dat', 'rb+') as persist_file:
                persist_data = persist_file.read()
                if persist_data:
                    persist_dict = pickle.loads(persist_data)
                    for item in in_stock:
                        if not persist_dict.get(item):
                            email_trigger = True
                elif in_stock:
                    email_trigger = True
                persist_dict = {item_name:True for item_name in in_stock}
                persist_dict.update({item_name:False for item_name in out_of_stock})
                persist_file.write(pickle.dumps(persist_dict))
        else:
            with open('items.dat', 'wb+') as persist_file:
                persist_dict = {item_name:True for item_name in in_stock}
                persist_dict.update({item_name:False for item_name in out_of_stock})
                persist_file.write(pickle.dumps(persist_dict))
            if in_stock:
                email_trigger = True
    else:
        email_trigger = True
    if config['general']['send_email_enabled'] and email_trigger:
        send_email(in_stock, out_of_stock)


def check_item_in_stock(item):
    response = requests.get(CHECK_URL.format(item)).json()
    item_name = response['response']['data']['boxDetails'][0]['boxName']

    return response['response']['data']['boxDetails'][0]['outOfStock'] == 0, item_name


def send_email(in_stock, out_of_stock):
    msg = MIMEMultipart("alternative")
    msg['Subject'] = "CEX stock check results. {0} items in stock".format(len(in_stock))
    msg['From'] = config['general']['email_send_from']
    msg['to'] = config['general']['to_email']


    html = MIMEText(
        str.format(
            EMAIL_HTML,
            in_stock,
            out_of_stock,
            config['general']['items'].split(',')
        )
    )
    msg.attach(html)

    server = smtplib.SMTP(config['general']['smtp_host'], config['general']['smtp_port'])
    server.ehlo()
    server.starttls()
    server.ehlo()
    server.login(config['general']['email_send_from'], config['general']['email_pass'])
    server.sendmail(config['general']['email_send_from'], config['general']['to_email'], msg.as_string())
    server.close()
    logger.info('Email sent to %s', config['general']['to_email'])

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Check cex stock for all items listed in the config.")
    parser.add_argument('--deamon', action='store_true',
                        help='In deamon mode, nothing will be output to screen')
    parser.add_argument('--config-path', help='Path to the config file, default to config.ini in the same folder as the script.', default='config.ini')
    parser.add_argument('--persist', help='Persist stock changes to a file, and only trigger an email if the stock has changed.', action='store_true')

    args = parser.parse_args()
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        fmt='%(asctime)-15s %(process)d %(levelname)s line %(lineno)d %(message)s', datefmt='%Y-%m-%dT%H:%M:%S')


    stdouthandler = logging.StreamHandler()
    stdouthandler.setFormatter(formatter)
    stdouthandler.setFormatter(formatter)
    logger.addHandler(stdouthandler)

    if os.path.isfile(args.config_path):
        config = ConfigParser()
        config.read(args.config_path)
        check_stock()
