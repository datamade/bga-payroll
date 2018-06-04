PG_DB=bga_payroll


database : $(PG_DB)

$(PG_DB) : data/output/2018-05-30-employer_taxonomy.csv illinois_places
	psql -U postgres -d $(PG_DB) -c "\d" > /dev/null 2>&1 || \
	(createdb -U postgres $@ && python manage.py makemigrations)

data/output/2018-05-30-employer_taxonomy.csv :
	python data/processors/get_taxonomy.py > $@

include data_samples.mk places.mk
