import csv
import datetime
import sys


reader = csv.DictReader(sys.stdin)
writer = csv.DictWriter(sys.stdout, fieldnames=reader.fieldnames)

writer.writeheader()

current_year = datetime.datetime.now().year

for row in reader:
    if row['date_started']:
        date_validated = False

        stripped_date = row['date_started'].strip()

        for date_format in ('%m/%d/%y', '%m/%d/%Y', '%Y-%m-%d'):
            try:
                start_date = datetime.datetime.strptime(stripped_date, date_format)
            except ValueError:  # invalid date
                continue
            else:
                if start_date.year > current_year:
                    # sometimes, start dates have the year but not the century,
                    # e.g., 68 instead of 1968. the computer misinterprets years
                    # prior to 1969, such that 68 becomes 2068 instead of 1968,
                    # etc. since these are start dates, and people can't have
                    # started jobs in the future, we know that this is in error.
                    continue

                else:
                    date_validated = True
                    break

        if not date_validated:
            # omit misformatted dates, e.g., 10/1/20007.
            sys.stderr.write('OMITTING INVALID DATE: {}\n'.format(stripped_date))

            row['date_started'] = ''

    writer.writerow(row)
