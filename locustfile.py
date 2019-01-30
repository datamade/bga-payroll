import csv
import itertools
import random
import time

from locust import HttpLocust, seq_task, TaskSequence
from lxml import etree
import requests


def _get_unit():
    with open('data/output/2018-09-12-employer_taxonomy.csv', 'r') as f:
        reader = csv.reader(f)
        next(reader)
        units = [row[0] for row in reader]

    return random.choice(units)


class WebsiteTasks(TaskSequence):
    def on_start(self):
        self.unit = _get_unit()

    @seq_task(1)
    def search_units(self):
        rv = self.client.get('/search/?entity_type=unit&name={}'.format(self.unit))
        assert rv.status_code == 200

        tree = etree.HTML(rv.content)
        self.search_results = [a.attrib['href'] for a in tree.xpath('//a[@class="search-result"]')]

    @seq_task(2)
    def view_unit(self):
        unit_url = random.choice(self.search_results)
        rv = self.client.get(unit_url)
        assert rv.status_code == 200

        tree = etree.HTML(rv.content)
        page_links = [a.attrib['href'] for a in tree.xpath('//a')]

        self.person_links = list(a for a in page_links if a.startswith('/person'))
        self.department_links = set(list(a for a in page_links if a.startswith('/department')))

    @seq_task(3)
    def browse_unit(self):
        for link in itertools.chain(self.person_links, self.department_links):
            rv = self.client.get(link)
            assert rv.status_code == 200

            time.sleep(1)


class WebsiteUser(HttpLocust):
    task_set = WebsiteTasks
    min_wait = 2500
    max_wait = 10000
