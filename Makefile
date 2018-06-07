PG_DB=bga_payroll


.PHONY : database migrations

database : migrations

$(PG_DB) :
	psql -U postgres -d $(PG_DB) -c "\d" > /dev/null 2>&1 || \
	createdb -U postgres $@

migrations : $(PG_DB)
	python manage.py migrate

include data_samples.mk
