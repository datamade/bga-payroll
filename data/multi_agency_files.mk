VPATH=data


.INTERMEDIATE : 2017-pt-%-with-agencies.csv 2017-pt-%-with-data-year.csv \
	2017-pt-%-with-valid-start-dates.csv 2017-pt-%-salary-summed.csv \
	2017-pt-%-no-salary-omitted.csv %-amendment-with-agencies.csv

2017-actual-pt-%.csv : 2017-pt-%-no-salary-omitted.csv
	(echo employer,last_name,first_name,title,department,base_salary,extra_pay,date_started,id,_,responding_agency,data_year,salary; \
	tail -n +2 $<) > $@

2017-pt-%-no-salary-omitted.csv : 2017-pt-%-salary-summed.csv
	csvgrep -c total_pay -r '^$$' -i $< > $@

2017-pt-%-salary-summed.csv : 2017-pt-%-with-valid-start-dates.csv
	cat $< | python data/processors/sum_salary.py > $@

2017-pt-%-with-valid-start-dates.csv : 2017-pt-%-with-data-year.csv
	# Remove invalid dates. (Only two in the first round.)
	cat $< | python data/processors/validate_dates.py > $@

2017-pt-%-with-data-year.csv : 2017-pt-%-with-agencies.csv
	# Add required data year field.
	perl -pe 's/$$/,2017/' $< > $@

2017-pt-%-with-agencies.csv : raw/2017-payroll-actual-pt-%.csv raw/foia-source-lookup.csv
	# Join standard data with agency lookup.
	csvjoin -c id,ID -e IBM852 $^ > $@
