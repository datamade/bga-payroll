import pickle

from django.db import connection

from saferedisqueue import SafeRedisQueue

from bga_database.settings import REDIS_URL
from data_import.utils.table_names import TableNamesMixin


class ReviewQueue(TableNamesMixin):
    def __init__(self, s_file_id):
        super().__init__(s_file_id)

        self.__q = SafeRedisQueue(url=REDIS_URL,
                                  name=self.q_name_fmt.format(s_file_id),
                                  autoclean_interval=150,
                                  serializer=pickle)

        from data_import.models import StandardizedFile
        s_file = StandardizedFile.objects.get(id=s_file_id)

        self.vintage = s_file.upload

    @property
    def remaining(self):
        return self.__q._redis.hlen(self.__q.ITEMS_KEY)

    def add(self, item):
        '''
        Add an item to the queue, for the first time.
        '''
        return self.__q.put(item)

    def checkout(self, timeout=-1):
        '''
        Get an item from the queue. By default, do not block.
        If blocking is desired, set :timeout to time in seconds
        to wait before returning None.
        '''
        return self.__q.get(timeout=timeout)

    def remove(self, uid):
        '''
        Remove the given item from the queue.
        '''
        return self.__q.ack(uid)

    def replace(self, uid):
        '''
        If an operation fails, put the given item back in
        the queue.
        '''
        return self.__q.fail(uid)

    def flush(self):
        empty = False

        while not empty:
            uid, item = self.checkout()

            if not item:
                empty = True
            else:
                item['id'] = uid
                self.match_or_create(item)

    def match_or_create(self):
        raise NotImplementedError


class RespondingAgencyQueue(ReviewQueue):
    q_name_fmt = 'responding_agency_queue_{}'

    def match_or_create(self, item, match=None):
        '''
        Given an item, and (optionally) a match, handle review
        decision, then remove the item from the queue.

        :item is a dictionary, where 'id' is the uid of the
        enqueued item.
        '''
        uid = item.pop('id')

        if match:
            with connection.cursor() as cursor:
                update = '''
                    UPDATE {raw_payroll}
                      SET responding_agency = '{match}'
                      WHERE responding_agency = '{unseen}'
                '''.format(raw_payroll=self.raw_payroll_table,
                           match=match,
                           unseen=item['name'])

                cursor.execute(update)

        else:
            from data_import.models import RespondingAgency
            RespondingAgency.objects.create(**item)

        self.remove(uid)


class ParentEmployerQueue(ReviewQueue):
    q_name_fmt = 'parent_employer_queue_{}'

    def match_or_create(self, item, match=None):
        '''
        Given an item, and (optionally) a match, handle review
        decision, then remove the item from the queue.

        :item is a dictionary, where 'id' is the uid of the
        enqueued item.
        '''
        uid = item.pop('id')

        if match:
            with connection.cursor() as cursor:
                update = '''
                    UPDATE {raw_payroll}
                      SET employer = '{match}'
                      WHERE employer = '{unseen}'
                '''.format(raw_payroll=self.raw_payroll_table,
                           match=match,
                           unseen=item['name'])

                cursor.execute(update)

        else:
            from payroll.models import Employer

            Employer.objects.create(name=item['name'],
                                    vintage=self.vintage)

        self.remove(uid)


class ChildEmployerQueue(ReviewQueue):
    q_name_fmt = 'child_employer_queue_{}'

    def match_or_create(self, item, match=None):
        '''
        Given an item, and (optionally) a match, handle review
        decision, then remove the item from the queue.

        :item is a dictionary, where 'id' is the uid of the
        enqueued item.
        '''
        uid = item.pop('id')

        if match:
            with connection.cursor() as cursor:
                update = '''
                    UPDATE {raw_payroll}
                      SET department = '{match}'
                      WHERE department = '{unseen_employer}'
                      AND employer = '{unseen_parent}'
                '''.format(raw_payroll=self.raw_payroll_table,
                           match=match,
                           unseen_employer=item['name'],
                           unseen_parent=item['parent'])

                cursor.execute(update)

        else:
            from payroll.models import Employer

            parent = Employer.objects.get(parent_id__isnull=True,
                                          name__iexact=item['parent'])

            Employer.objects.create(name=item['name'],
                                    parent=parent,
                                    vintage=self.vintage)

        self.remove(uid)


class SalaryQueue(ReviewQueue):
    q_name_fmt = 'salary_queue_{}'
