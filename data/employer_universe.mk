data/output/fire_departments.csv :
	# Assumes 2017 payroll data has been imported into your database
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
		) TO STDOUT CSV HEADER" > $@