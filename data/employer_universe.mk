# These recipes assume 2017 payroll data has been imported into your database.

data/output/fire_departments.csv :
	psql -d bga_payroll -c " \
		COPY ( \
		  SELECT \
		    NULL AS parent, \
		    name AS employer \
		  FROM payroll_employer \
		  WHERE name ~* '.*(fp?d|fire.*)$$' \
		  AND parent_id IS NULL \
		  UNION ALL \
		  SELECT \
		    parent.name AS parent, \
		    child.name AS employer \
		  FROM payroll_employer AS child \
		  JOIN payroll_employer AS parent \
		  ON child.parent_id = parent.id \
		  WHERE child.name ~* '.*(fp?d|fire.*)$$' \
		  AND child.parent_id IS NOT NULL \
		  /* FPDs are included in the universe already */ \
		  AND parent.name NOT ILIKE '%fpd' \
		) TO STDOUT CSV HEADER" > $@

data/output/police_departments.csv :
	psql -d bga_payroll -c " \
		COPY ( \
		  SELECT \
		    parent.name AS parent, \
		    child.name AS employer \
		  FROM payroll_employer AS child \
		  JOIN payroll_employer AS parent \
		  ON child.parent_id = parent.id \
		  WHERE child.name ~* '.*((?<!f)pd|police).*$$' \
		) TO STDOUT CSV HEADER" > $@
