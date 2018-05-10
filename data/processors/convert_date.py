import csv
from datetime import datetime
import sys


reader = csv.reader(sys.stdin)
writer = csv.writer(sys.stdout)

for row in reader:
    start_date = datetime.fromtimestamp(float(row[7]))
    row[7] = '{0}-{1}-{2}'.format(start_date.year, start_date.month, start_date.day)
    writer.writerow(row)