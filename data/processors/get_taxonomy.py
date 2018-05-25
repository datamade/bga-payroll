import csv
import sys

import requests
from lxml import etree


writer = csv.writer(sys.stdout)

writer.writerow(['entity', 'entity_type'])

if __name__ == '__main__':
    page = requests.get('https://www.bettergov.org/payroll-database')
    tree = etree.HTML(page.text)
    select = tree.xpath('//div[contains(@class, "form-item-employer")]/select')[0]

    for group in select.iterchildren():
        if group.attrib.get('label'):
            entity_type = group.attrib.get('label')

            for unit in group.iterchildren():
                writer.writerow([unit.text, entity_type])
