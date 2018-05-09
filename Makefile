PG_DB=bga_payroll


database : $(PG_DB)

$(PG_DB) :
	psql -d $(PG_DB) -c "\d" > /dev/null 2>&1 || ( \
	createdb $@ && \
	python manage.py migrate)
