import csv
import sys


reader = csv.DictReader(sys.stdin)
output_fieldnames = reader.fieldnames + ['total_pay']
writer = csv.DictWriter(sys.stdout, fieldnames=output_fieldnames)

writer.writeheader()


def float_from_pay(input_pay):
    if input_pay:
        try:
            output_pay = float(input_pay)
        except (TypeError, ValueError):
            raise
    else:
        output_pay = None

    return output_pay


for row in reader:
    base_pay = float_from_pay(row['base_salary'])
    extra_pay = float_from_pay(row['extra_pay'])

    if base_pay and extra_pay:
        row['total_pay'] = base_pay + extra_pay
    elif base_pay:
        row['total_pay'] = base_pay
    elif extra_pay:
        row['total_pay'] = extra_pay

    writer.writerow(row)
