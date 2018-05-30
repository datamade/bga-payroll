import csv
import sys

import requests
from lxml import etree


writer = csv.writer(sys.stdout)
writer.writerow(['entity', 'entity_type', 'chicago', 'cook_or_collar'])

discard = ['Wisconsin', 'Indiana']

unmapped_entities = [
    ('Elburn Countryside FPD', 'Fire Protection District', False, False),
    ('Iverness Park District', 'Parks District', False, False),
    ('River East Library District', 'Library District', False, False),
    ('Steger-South Chicago Heights Library District', 'Library District', False, False),
]

entity_map = {
    'Chicago': ('Municipal', False),
    'Chicago-Area Counties': ('County', True),
    'Cook County Townships': ('Township', True),
    'Downstate Counties': ('County', False),
    'Fire Protection Districts': ('Fire Protection District', False),
    'Library Districts': ('Library District', False),
    'Park Districts': ('Parks District', False),
    'Public Education': ('Education', False),
    'Regional': ('Regional', False),
    'State': ('State', False),
    'Suburban/Downstate Municipal': ('Municipal', False),
    'Suburban/Downstate Townships': ('Township', False),
}

if __name__ == '__main__':
    page = requests.get('https://www.bettergov.org/payroll-database')
    tree = etree.HTML(page.text)
    select = tree.xpath('//div[contains(@class, "form-item-employer")]/select')[0]

    for group in select.iterchildren():
        if group.attrib.get('label'):
            entity_type = group.attrib.get('label')

            if entity_type in discard:
                continue

            formatted_entity_type, cook_or_collar = entity_map[entity_type]

            if entity_type == 'Chicago':
                chicago = True
            else:
                chicago = False

            for unit in group.iterchildren():

                if any(substr in unit.text.lower()
                       for substr in ('conservation', 'forest preserve')):

                    formatted_entity_type = 'Forest Preserve'
                    cook_or_collar = False

                writer.writerow([
                    unit.text,
                    formatted_entity_type,
                    chicago,
                    cook_or_collar,
                ])

    for entity in unmapped_entities:
        writer.writerow(entity)
