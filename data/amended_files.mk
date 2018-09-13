VPATH=data


.INTERMEDIATE : %-amendment-with-data-year.csv \
	%-amendment-with-valid-start-dates.csv %-amendment-salary-summed.csv \
	%-amendment-no-salary-omitted.csv

%-amendment.csv : %-amendment-no-salary-omitted.csv
	(echo employer,last_name,first_name,title,department,base_salary,extra_pay,date_started,id,_,responding_agency,data_year,salary; \
	tail -n +2 $<) > $@

%-amendment-no-salary-omitted.csv : %-amendment-salary-summed.csv
	csvgrep -c total_pay -r '^$$' -i $< > $@

%-amendment-salary-summed.csv : %-amendment-with-valid-start-dates.csv
	cat $< | python data/processors/sum_salary.py > $@

%-amendment-with-valid-start-dates.csv : %-amendment-with-data-year.csv
	# Remove invalid dates. (Only two in the first round.)
	cat $< | python data/processors/validate_dates.py > $@

%-amendment-with-data-year.csv : %-amendment-with-agencies.csv
	# Add required data year field.
	perl -pe 's/$$/,2017/' $< > $@

%-amendment-with-agencies.csv : raw/%-amendment.csv raw/foia-source-lookup.csv
	# Join standard data with agency lookup.
	csvjoin -c id,ID -e IBM852 $^ > $@
