PG_DB=bga_payroll


database : migrations

$(PG_DB) :
	psql -U postgres -d $(PG_DB) -c "\d" > /dev/null 2>&1 || \
	createdb -U postgres $@

employer_taxonomy : $(PG_DB)
	psql -U postgres -d $< -c "\d $@" > /dev/null 2>&1 || \
 	(python data/processors/get_taxonomy.py | \
 	csvsql --db postgresql:///$(PG_DB) --insert --table $@)

migrations : employer_taxonomy
	python manage.py migrate

include data_samples.mk
