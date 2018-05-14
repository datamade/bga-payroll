VPATH=data
SAMPLE_HEADER=responding_agency,employer,department,last_name,first_name,title,\
	salary,date_started,data_year


.INTERMEDIATE : 2016-formatted.csv 2017-formatted.csv

samples : data/output/2016-sample-a.csv data/output/2016-sample-b.csv \
	data/output/2017-sample-a.csv


data/output/2017-sample-a.csv : 2017-formatted.csv
	head -n 5000 $< > $@

data/output/2016-sample-a.csv : 2016-formatted.csv
	head -n 2500 $< > $@

data/output/2016-sample-b.csv : 2016-formatted.csv
	tail -n 300000 $< | (echo $(SAMPLE_HEADER); head -n 3450) > $@

2016-formatted.csv : raw/2016_payroll.csv
	csvcut -c 12,12,6,4,3,5,7,8,11 -e ISO-8859-1 $< | tail +2 | \
	(echo $(SAMPLE_HEADER); python data/processors/convert_date.py) > $@

2017-formatted.csv : raw/2017_payroll.csv
	csvcut -c 2,2,3,4,5,6,7,8,9 -e WINDOWS-1250 $< | \
	perl -pe 's/Employer/Responding Agency/' > $@
