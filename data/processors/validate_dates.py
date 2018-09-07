import csv
import datetime
import sys


reader = csv.reader(sys.stdin)
writer = csv.writer(sys.stdout)

writer.writerow(next(reader))

for row in reader:
    if row[-5]:
        try:
            datetime.datetime.strptime(row[-5], '%m/%d/%y')
        except ValueError:  # invalid date
            row[-5] = ''

    writer.writerow(row)