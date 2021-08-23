SHELL := bash
.SHELLFLAGS := -eu -o pipefail

PG_DB=bga_payroll

.PHONY : clean database

clean :
	rm *.csv

database : $(PG_DB)

$(PG_DB) :
	psql -U postgres -d $(PG_DB) -c "\d" > /dev/null 2>&1 || \
	createdb -U postgres $@

include data/payroll.mk
