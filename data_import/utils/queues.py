import pickle

from django.conf import settings
from saferedisqueue import SafeRedisQueue

from data_import.utils.table_names import TableNamesMixin


class ReviewQueue(TableNamesMixin):
    def __init__(self, s_file_id):
        super().__init__(s_file_id)

        self.__q = SafeRedisQueue(url=settings.REDIS_URL,
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
        '''
        Remove everything from the queue.
        '''
        self.__q._redis.flushdb()

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
            from data_import.models import RespondingAgencyAlias

            RespondingAgencyAlias.objects.create(
                name=item['name'],
                responding_agency_id=match
            )

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
            from payroll.models import EmployerAlias

            EmployerAlias.objects.create(
                name=item['name'],
                employer_id=match
            )

        self.remove(uid)


class ChildEmployerQueue(ParentEmployerQueue):
    q_name_fmt = 'child_employer_queue_{}'
