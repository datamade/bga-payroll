import csv
import datetime
import sys


reader = csv.reader(sys.stdin)
writer = csv.writer(sys.stdout)

writer.writerow(next(reader))

for row in reader:
    if row[-5]:
        date_validated = False

        for date_format in ('%m/%d/%y', '%m/%d/%Y', '%Y-%m-%d'):
            try:
                datetime.datetime.strptime(row[-5], date_format)
            except ValueError:  # invalid date
                continue
            else:
                date_validated = True
                break

        if not date_validated:
            sys.stderr.write('{}\n'.format(row[-5]))
            row[-5] = ''

        writer.writerow(row)
