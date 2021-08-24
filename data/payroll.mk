.INTERMEDIATE : %-with-agencies.csv %-with-data-year.csv \
	%-with-valid-start-dates.csv %-salary-summed.csv \
	%-no-salary-omitted.csv %-with-agencies.csv

.PRECIOUS : %-with-agencies.csv data/output/%

import/% : data/output/%
	python manage.py import_data --data_file $< \
		--reporting_year $$(echo "$<" | grep -Eo "[0-9]{4}")

amend/% : data/output/%
	python manage.py import_data --data_file $< \
		--reporting_year $$(echo "$<" | grep -Eo "[0-9]{4}") \
		--amend

data/output/payroll-actual-%.csv : %-with-data-year.csv
	# Rename fields.
	(echo employer,last_name,first_name,title,department,base_salary,extra_pay,date_started,id,_,responding_agency,data_year; \
	tail -n +2 $<) > $@

%-with-data-year.csv : %-leading-whitespace-trimmed.csv
	# Add required data year field.
	perl -pe "s/$$/,$$(cut -d '-' -f 1 <<< $*)/" $< > $@

%-leading-whitespace-trimmed.csv : %-no-salary-omitted.csv
	perl -pe 's/^\s+//' $< > $@

%-no-salary-omitted.csv : %-with-valid-start-dates.csv
	# Remove records where no salary was reported and validate that the output
	# file has the expected number of lines.
	csvgrep -c base_salary,extra_pay -r '^$$' -i $< > $@; \
	N_REMOVED=$$(csvgrep -c base_salary,extra_pay -r '^$$' $< | tail -n +2 | wc -l | xargs); \
	echo "Removed $$N_REMOVED records without salary"; \
	EXPECTED_LINES=$$(expr $$(grep . $< | wc -l | grep -Eo '[0-9]+' | head -n 1) - $$N_REMOVED); \
	OUTFILE_LINES=$$(grep . $@ | wc -l | grep -Eo '[0-9]+' | head -n 1); \
	if [ $$EXPECTED_LINES -eq $$OUTFILE_LINES ]; then \
		echo "Outfile has expected number of lines. Proceeding..."; \
	else \
		echo "Expected $$EXPECTED_LINES lines in $@, but found $$OUTFILE_LINES. Investigate the discrepancy..."; \
		exit 1; \
	fi

%-with-valid-start-dates.csv : %-with-agencies.csv
	# Remove invalid dates.
	cat $< | python data/processors/validate_dates.py > $@

%-with-agencies.csv : data/raw/payroll-actual-%.csv data/raw/foia-source-lookup.csv
	# Join standard data with agency lookup and validate that the output file
	# has the expected number of lines.
	csvjoin -c id,ID -e IBM852 $^ > $@ && \
	INFILE_LINES=$$(grep . $< | wc -l | grep -Eo '[0-9]+' | head -n 1); \
	OUTFILE_LINES=$$(grep . $@ | wc -l | grep -Eo '[0-9]+' | head -n 1); \
	if [ $$INFILE_LINES -eq $$OUTFILE_LINES ]; then \
		echo "No lines lost in join. Proceeding..."; \
	else \
		echo "$< has $$INFILE_LINES lines, but $@ has $$OUTFILE_LINES lines. Generating missing agencies..."; \
		make $*-missing-agencies.csv; \
	fi

%-missing-agencies.csv : data/raw/payroll-actual-%.csv data/raw/foia-source-lookup.csv
	# If this recipe fires, one or more responding agencies cited in incoming
	# data are missing from the FOIA source lookup. The output contains their
	# id and employer name. Either the lookup table needs to be updated, or the
	# data needs to be amended to reference an existing code.
	csvjoin --left -c id,ID -e IBM852 $^ | \
	csvgrep -c Employer -r "^$$" | \
	csvcut -c 1,9 | uniq > $@; \
	echo "Contact the BGA for clarification on agencies missing from the lookup table."; \
	exit 1
