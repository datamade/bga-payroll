VPATH=data
SAMPLE_HEADER=responding_agency,employer,department,last_name,first_name,title,\
	salary,date_started,data_year


.INTERMEDIATE : 2016-formatted.csv 2017-formatted.csv

samples : data/output/2016-sample.csv data/output/2017-sample.csv


data/output/2016-sample.csv : 2016-formatted.csv
	head -n 5000 $< > $@

data/output/2017-sample.csv : 2017-formatted.csv
	csvgrep -c Employer -r "(ACORN LIBRARY DISTRICT|ADAMS COUNTY|FOX RIVER GROVE FIRE PROTECTION DISTRICT)" $< > $@

2016-formatted.csv : raw/2016_payroll.csv
	csvcut -c 12,12,6,4,3,5,7,8,11 -e ISO-8859-1 $< | tail +2 | \
	(echo $(SAMPLE_HEADER); python data/processors/convert_date.py) > $@

2017-formatted.csv : raw/2017_payroll.csv
	csvcut -c 2,2,3,4,5,6,7,8,9 -e WINDOWS-1250 $< | \
	perl -pe 's/Employer/Responding Agency/' > $@

2017-actual-formatted.csv : raw/2017_payroll_actual.csv
	csvcut -c 2,2,3,4,5,6,7,8,9,10 $< | \
	csvgrep -c 1 -ir '^$$'| \
	perl -pe 's/Employer/Responding Agency/' | \
	tr -s " " > $@
