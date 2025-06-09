INSERT INTO search_employersearchindex (
    instance_id,
    search_name,
    reporting_year,
    headcount,
    expenditure
)
SELECT
    COALESCE(employer.parent_id, employer.id) AS instance_id,
    COALESCE(parent_employer.name, employer.name) AS s_search_name,
    s_file.reporting_year AS reporting_year,
    COUNT(job_id) AS headcount,
    SUM(COALESCE(salary.amount, 0) + COALESCE(salary.extra_pay, 0)) AS expenditure
FROM payroll_salary salary
INNER JOIN payroll_job job ON salary.job_id = job.id
INNER JOIN payroll_position position ON job.position_id = position.id
INNER JOIN data_import_upload upload ON salary.vintage_id = upload.id
INNER JOIN data_import_standardizedfile s_file ON upload.id = s_file.upload_id
INNER JOIN payroll_employer employer ON position.employer_id = employer.id
LEFT JOIN payroll_employer parent_employer ON employer.parent_id = parent_employer.id
GROUP BY instance_id, s_search_name, reporting_year
ON CONFLICT (instance_id, reporting_year) DO UPDATE
SET
    headcount = EXCLUDED.headcount,
    expenditure = EXCLUDED.expenditure;

INSERT INTO search_employersearchindex (
    instance_id,
    search_name,
    reporting_year,
    headcount,
    expenditure
)
SELECT
    employer.id AS instance_id,
    parent_employer.name || ' ' || employer.name AS s_search_name,
    s_file.reporting_year AS reporting_year,
    COUNT(job_id) AS headcount,
    SUM(COALESCE(salary.amount, 0) + COALESCE(salary.extra_pay, 0)) AS expenditure
FROM payroll_salary salary
INNER JOIN payroll_job job ON salary.job_id = job.id
INNER JOIN payroll_position position ON job.position_id = position.id
INNER JOIN data_import_upload upload ON salary.vintage_id = upload.id
INNER JOIN data_import_standardizedfile s_file ON upload.id = s_file.upload_id
INNER JOIN payroll_employer employer ON position.employer_id = employer.id
JOIN payroll_employer parent_employer ON employer.parent_id = parent_employer.id
GROUP BY instance_id, s_search_name, reporting_year
ON CONFLICT (instance_id, reporting_year) DO UPDATE
SET
    headcount = EXCLUDED.headcount,
    expenditure = EXCLUDED.expenditure;
