from django.db import connection


class ImportUtility(object):

    @classmethod
    def _create_table(cls, table_name, columns):
        with connection.cursor() as cursor:
            cursor.execute(
                'CREATE TABLE {} ({})'.format(table_name, columns)
            )

    def select_employers(self):
        pass
