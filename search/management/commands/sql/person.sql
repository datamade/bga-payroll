INSERT INTO search_personsearchindex (
    instance_id,
    reporting_year,
    search_name,
    search_title,
    total_pay,
    employer_id
)
SELECT DISTINCT ON (instance_id)
  person.id AS instance_id,
  s_file.reporting_year,
  COALESCE(person.first_name || ' ' || person.last_name, 'EMPLOYEE') AS search_name,
  esi.search_name || ' ' || position.title AS search_title,
  COALESCE(salary.amount, 0) + COALESCE(salary.extra_pay, 0) AS total_pay,
  employer.slug AS employer_id
FROM payroll_job AS job
JOIN payroll_salary AS salary
ON salary.job_id = job.id
JOIN payroll_position AS position
ON job.position_id = position.id
JOIN payroll_person AS person
ON job.person_id = person.id
JOIN payroll_employer as employer
ON position.employer_id = employer.id
JOIN search_employersearchindex AS esi
ON employer.id = esi.instance_id
JOIN data_import_upload upload
ON salary.vintage_id = upload.id
JOIN data_import_standardizedfile s_file 
ON upload.id = s_file.upload_id
ON CONFLICT (instance_id, reporting_year) DO UPDATE
SET
    search_name = EXCLUDED.search_name,
    search_title = EXCLUDED.search_title,
    total_pay = EXCLUDED.total_pay,
    employer_id = EXCLUDED.employer_id;