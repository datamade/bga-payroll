VPATH=data
SAMPLE_HEADER=responding_agency,employer,department,last_name,first_name,title,\
	salary,date_started,data_year


2017-actual-pt-1.csv : 2017-no-salary-omitted.csv
	(echo employer,last_name,first_name,title,department,salary,extra_pay,date_started,id,_,responding_agency,data_year; \
	tail -n +2 $<) > $@

2017-no-salary-omitted.csv : 2017-with-valid-start-dates.csv
	csvgrep -c base_salary -r '^$$' -i $< > $@

2017-with-valid-start-dates.csv : 2017-with-data-year.csv
	# Remove invalid dates. (Only two in the first round.)
	cat $< | python data/processors/validate_dates.py > $@

2017-with-data-year.csv : 2017-with-agencies.csv
	# Add required data year field.
	perl -pe 's/$$/,2017/' $< > $@

2017-with-agencies.csv : raw/2017-payroll-actual-pt-1.csv raw/foia-source-lookup.csv
	# Join standard data with agency lookup.
	csvjoin -c id,ID -e IBM852 $^ > $@

2016-formatted.csv : raw/2016_payroll.csv
	csvcut -c 12,12,6,4,3,5,7,8,11 -e ISO-8859-1 $< | tail +2 | \
	(echo $(SAMPLE_HEADER); python data/processors/convert_date.py) > $@

2017-formatted.csv : raw/2017_payroll.csv
	csvcut -c 2,2,3,4,5,6,7,8,9 -e WINDOWS-1250 $< | \
	perl -pe 's/Employer/Responding Agency/' > $@
