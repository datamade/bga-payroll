class TableNamesMixin(object):
    def __init__(self, s_file_id):
        self.raw_payroll_table = 'raw_payroll_{}'.format(s_file_id)
        self.raw_job_table = 'raw_job_{}'.format(s_file_id)
        self.raw_person_table = 'raw_person_{}'.format(s_file_id)
