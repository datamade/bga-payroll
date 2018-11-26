VPATH=data
SAMPLE_HEADER=responding_agency,employer,department,last_name,first_name,title,\
	salary,date_started,data_year


2016-formatted.csv : raw/legacy/2016_payroll.csv
	csvcut -c 12,12,6,4,3,5,7,8,11 -e ISO-8859-1 $< | tail +2 | \
	(echo $(SAMPLE_HEADER); python data/processors/convert_date.py) > $@

2017-formatted.csv : raw/legacy/2017_payroll.csv
	csvcut -c 2,2,3,4,5,6,7,8,9 -e WINDOWS-1250 $< | \
	perl -pe 's/Employer/Responding Agency/' > $@
