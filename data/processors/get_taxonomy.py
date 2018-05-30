import csv
import sys

import requests
from lxml import etree


class PayrollDatabaseScraper(object):
    DISCARD = [
        'Wisconsin',
        'Indiana',
    ]

    ENTITY_MAP = {
        'Chicago': 'Municipal',
        'Chicago-Area Counties': 'County',
        'Cook County Townships': 'Township',
        'Downstate Counties': 'County',
        'Fire Protection Districts': 'Fire Protection District',
        'Library Districts': 'Library District',
        'Park Districts': 'Parks District',
        'Public Education': 'Education',
        'Regional': 'Regional',
        'State': 'State',
        'Suburban/Downstate Municipal': 'Municipal',
        'Suburban/Downstate Townships': 'Township',
    }

    UNMAPPED_ENTITIES = [
        ('Elburn Countryside FPD', 'Fire Protection District', False, False),
        ('Iverness Park District', 'Parks District', False, False),
        ('River East Library District', 'Library District', False, False),
        ('Steger-South Chicago Heights Library District', 'Library District', False, False),
    ]

    def _is_cook_or_collar(self, entity_type):
        return entity_type.lower() in ('chicago-area counties',
                                       'cook county townships')

    def _is_chicago(self, entity_type):
        return entity_type.lower() == 'chicago'

    def _is_forest_preserve(self, entity):
        return any(substr in entity.lower() for substr in ('conservation',
                                                           'forest preserve'))

    def classifications(self):
        page = requests.get('https://www.bettergov.org/payroll-database')
        tree = etree.HTML(page.text)

        select = tree.xpath('//div[contains(@class, "form-item-employer")]/select')[0]

        yield from select.iterchildren()

    def scrape(self):
        writer = csv.writer(sys.stdout)
        writer.writerow(['entity', 'entity_type', 'chicago', 'cook_or_collar'])

        for classification in self.classifications():
            if classification.attrib.get('label'):
                entity_type = classification.attrib.get('label')

                if entity_type in self.DISCARD:
                    continue

                for entity in classification.iterchildren():
                    formatted_entity_type = self.ENTITY_MAP[entity_type]

                    chicago = self._is_chicago(entity_type)
                    cook_or_collar = self._is_cook_or_collar(entity_type)

                    if self._is_forest_preserve(entity.text):
                        formatted_entity_type = 'Forest Preserve'
                        cook_or_collar = False

                    writer.writerow([
                        entity.text,
                        formatted_entity_type,
                        chicago,
                        cook_or_collar,
                    ])

        for entity in self.UNMAPPED_ENTITIES:
            writer.writerow(entity)

if __name__ == '__main__':
    pds = PayrollDatabaseScraper()
    pds.scrape()
