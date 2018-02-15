PG_DB=bga_payroll
INPUT=payroll/management/commands/2017_payroll.sorted.csv


.INTERMEDIATE : $(INPUT)

database : $(PG_DB) inserts

# Sort by employer, department, title, first name, last name and remove duplicates
$(INPUT) : raw/2017_payroll.csv
	export LC_ALL='C'; \
	tail +2 $< | \
	sort --field-separator=',' -k2 -k6 -k5 -k4 -k3 | \
	uniq > $@

$(PG_DB) :
	psql -d $(PG_DB) -c "\d" > /dev/null 2>&1 || ( \
	createdb $@ && \
	psql -d $(PG_DB) -c 'CREATE EXTENSION IF NOT EXISTS "uuid-ossp"' && \
	python manage.py migrate)

inserts : $(INPUT)
	python manage.py import_data