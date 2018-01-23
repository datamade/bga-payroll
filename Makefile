PG_DB=bga

payroll : raw/2016_payroll.csv
	psql -d $(PG_DB) -c " \
		CREATE TABLE IF NOT EXISTS $@ ( \
			record INT, \
			agency_number INT, \
			first_name VARCHAR, \
			last_name VARCHAR, \
			title VARCHAR, \
			department VARCHAR, \
			salary DECIMAL, \
			date_started BIGINT, \
			year INT, \
			employer VARCHAR, \
			upload_date DATE, \
			upload_date_and_time TIMESTAMP \
		)"; \
	csvcut -c 1,2,3,4,5,6,7,8,11,12,13,14 $< | \
	tail -n +2 | \
	psql -d $(PG_DB) -c "COPY $@ FROM STDIN CSV"
