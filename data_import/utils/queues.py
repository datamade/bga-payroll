import pickle

from django.db import connection

from saferedisqueue import SafeRedisQueue

from bga_database.settings import REDIS_URL
from data_import.models import RespondingAgency
from data_import.utils.table_names import TableNamesMixin


class ReviewQueue(TableNamesMixin):
    def __init__(self, s_file_id):
        super().__init__(s_file_id)

        self.__q = SafeRedisQueue(url=REDIS_URL,
                                  name=self.q_name,
                                  autoclean_interval=600)

    @property
    def remaining(self):
        return self.__q._redis.hlen(self.__q.ITEMS_KEY)

    def add(self, item):
        '''
        Add an item to the queue, for the first time.
        '''
        if type(item) == dict:
            item = pickle.dumps(item)

        return self.__q.put(item)

    def checkout(self, timeout=3):
        '''
        Get an item from the queue. If there are no items,
        block for three seconds, then return.
        '''
        uid, item = self.__q.get(timeout=timeout)

        if type(item) == bytes:
            item = pickle.loads(item)

        return uid, item

    def remove(self, item, match=None):
        '''
        If an operation succeeds, remove the given item
        from the queue.
        '''
        uid = item.pop('id')

        if match:
            with connection.cursor() as cursor:
                update = '''
                    UPDATE {raw_payroll}
                      SET responding_agency = {match}
                      WHERE responding_agency = {unseen}
                '''.format(raw_payroll=self.raw_payroll_table,
                           match=match,
                           unseen=item['name'])

                cursor.execute(update)

        else:
            RespondingAgency.objects.create(**item)

        return self.__q.ack(uid)

    def replace(self, item):
        '''
        If an operation fails, put the given item back in
        the queue.
        '''
        uid = item.pop('id')

        return self.__q.fail(uid)


class RespondingAgencyQueue(ReviewQueue):
    q_name = 'responding_agency_queue'


class EmployerQueue(ReviewQueue):
    q_name = 'employer_queue'


class SalaryQueue(ReviewQueue):
    q_name = 'salary_queue'
