VPATH=data


.INTERMEDIATE : %-with-agencies.csv %-with-data-year.csv \
	%-with-valid-start-dates.csv %-salary-summed.csv \
	%-no-salary-omitted.csv %-amendment-with-agencies.csv

payroll-actual-%.csv : %-no-salary-omitted.csv
	# Rename fields.
	(echo employer,last_name,first_name,title,department,base_salary,extra_pay,date_started,id,_,responding_agency,data_year; \
	tail -n +2 $<) > $@

%-no-salary-omitted.csv : %-with-valid-start-dates.csv
	# Remove records where no salary was reported.
	csvgrep -c base_salary,extra_pay -r '^$$' -i $< > $@;
	echo "Removed $$(csvgrep -c base_salary,extra_pay -r '^$$' $< | wc -l | xargs) records without salary"

%-with-valid-start-dates.csv : %-with-data-year.csv
	# Remove invalid dates.
	cat $< | python data/processors/validate_dates.py > $@

%-with-data-year.csv : %-with-agencies.csv
	# Add required data year field.
	perl -pe "s/$$/,$$(cut -d '-' -f 1 <<< $*)/" $< > $@

%-with-agencies.csv : raw/payroll-actual-%.csv raw/foia-source-lookup.csv
	# Join standard data with agency lookup.
	csvjoin -c id,ID -e IBM852 $^ > $@
