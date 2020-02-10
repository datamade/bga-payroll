SHELL := bash
PG_DB=bga_payroll

.PHONY : all clean database

all : 2017 2018

2017 : $(patsubst %, payroll-actual-2017-pt-%.csv, 1 2 3)

2018 : payroll-actual-2018-pt-1.csv

clean :
	rm *.csv

database : $(PG_DB)

$(PG_DB) :
	psql -U postgres -d $(PG_DB) -c "\d" > /dev/null 2>&1 || \
	createdb -U postgres $@

include data/multi_agency_files.mk data/amended_files.mk
