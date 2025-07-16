from django.core.management.base import BaseCommand
from django.db.models import Sum, Q
from django.db.models.functions import Coalesce
from django.db import connection
import pysolr

from django.conf import settings

from data_import.models import StandardizedFile
from payroll.models import Employer, Person, Salary


class Command(BaseCommand):
    help = "Populate the Solr index"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.searcher = pysolr.Solr(settings.SOLR_URL)

    def add_arguments(self, parser):
        parser.add_argument(
            "--entity-types",
            dest="entity_types",
            help="Comma separated list of entity types to index",
            default="units,departments,people",
        )
        parser.add_argument(
            "--recreate",
            action="store_true",
            dest="recreate",
            default=False,
            help="Delete all existing documents before creating the search index",
        )
        parser.add_argument(
            "--chunksize",
            dest="chunksize",
            default=10000,
            help="Number of documents to add at once",
        )
        parser.add_argument(
            "--employer",
            default=None,
            help="ID of specific Employer instance to reindex",
        )
        parser.add_argument(
            "--person", default=None, help="ID of specific Person instance to reindex"
        )
        parser.add_argument(
            "--reporting_year",
            type=int,
            dest="reporting_year",
            default=None,
            help="Specify a specific reporting year to index",
        )
        parser.add_argument(
            "--s_file",
            dest="s_file_id",
            default=None,
            help="Specify a specific standardized file to index",
        )

    def handle(self, *args, **options):
        if options.get("reporting_year"):
            self.reporting_years = [options["reporting_year"]]
        else:
            self.reporting_years = list(
                StandardizedFile.objects.distinct("reporting_year").values_list(
                    "reporting_year", flat=True
                )
            )

        self.stdout.write(
            "Building index for reporting years: {}".format(self.reporting_years)
        )

        if options["employer"]:
            self.reindex_one("employer", options["employer"])
        elif options["person"]:
            self.reindex_one("person", options["person"])
        else:
            self.recreate = options["recreate"]
            self.chunksize = int(options["chunksize"])

            entities = options["entity_types"].split(",")

            for entity in entities:
                getattr(self, "index_{}".format(entity))()

    def _make_search_string(self, initial_params):
        search_fmt = "{initial_params} AND ({year_params})"
        year_params = " OR ".join(
            "year:{}".format(year) for year in self.reporting_years
        )
        return search_fmt.format(initial_params=initial_params, year_params=year_params)

    def index_units(self):
        if self.recreate:
            message = "Dropping units from {} from index".format(
                ", ".join(str(year) for year in self.reporting_years)
            )
            self.stdout.write(message)
            search_string = self._make_search_string("id:unit*")
            self.searcher.delete(q=search_string)
            self.stdout.write(self.style.SUCCESS("Units dropped from index"))

        self.stdout.write("Indexing units")

        sql = """
        WITH unit_stats AS (
            SELECT
                e.id as employer_id,
                e.name,
                e.slug,
                et.entity_type as taxonomy,
                ep.population,
                sf.reporting_year,
                COUNT(s.id) as headcount,
                SUM(COALESCE(s.amount, 0) + COALESCE(s.extra_pay, 0)) as expenditure
            FROM payroll_employer e
            LEFT JOIN payroll_employertaxonomy et ON e.taxonomy_id = et.id
            LEFT JOIN payroll_employerpopulation ep ON e.id = ep.employer_id
            LEFT JOIN payroll_position p ON (e.id = p.employer_id OR e.id = (
                SELECT parent_id FROM payroll_employer WHERE id = p.employer_id
            ))
            LEFT JOIN payroll_job j ON p.id = j.position_id
            LEFT JOIN payroll_salary s ON j.id = s.job_id
            LEFT JOIN data_import_upload u ON s.vintage_id = u.id
            LEFT JOIN data_import_standardizedfile sf ON u.id = sf.upload_id
            WHERE e.parent_id IS NULL
            AND sf.reporting_year = ANY(%s)
            GROUP BY e.id, e.name, e.slug, et.entity_type, ep.population, sf.reporting_year
            HAVING COUNT(s.id) > 0
        )
        SELECT
            employer_id,
            name,
            slug,
            taxonomy,
            reporting_year,
            expenditure,
            headcount,
            CASE
                WHEN population >= 1000000 THEN 'Large'
                WHEN population >= 50000 THEN 'Medium'
                WHEN population >= 10000 THEN 'Small'
                ELSE NULL
            END as size_class
        FROM unit_stats
        ORDER BY employer_id, reporting_year
        """

        documents = []
        document_count = 0

        with connection.cursor() as cursor:
            cursor.execute(sql, [self.reporting_years])

            for row in cursor:
                (
                    employer_id,
                    name,
                    slug,
                    taxonomy,
                    year,
                    expenditure,
                    headcount,
                    size_class,
                ) = row

                if headcount and expenditure:  # Only index units with actual data
                    document = {
                        "id": "unit.{}.{}".format(employer_id, year),
                        "slug": slug,
                        "name": name,
                        "entity_type": "Employer",
                        "year": year,
                        "taxonomy_s": taxonomy or "",
                        "size_class_s": size_class or "",
                        "expenditure_d": float(expenditure),
                        "headcount_i": headcount,
                        "text": name,
                    }

                    documents.append(document)

                    if len(documents) >= self.chunksize:
                        self.searcher.add(documents)
                        document_count += len(documents)
                        documents = []
                        self.stdout.write(
                            "Indexed {} unit documents...".format(document_count)
                        )

        if documents:
            self.searcher.add(documents)
            document_count += len(documents)

        self.stdout.write(
            self.style.SUCCESS(
                "Added {} unit documents to the index".format(document_count)
            )
        )

    def index_departments(self):
        if self.recreate:
            message = "Dropping departments from {} from index".format(
                ", ".join(str(year) for year in self.reporting_years)
            )
            self.stdout.write(message)
            search_string = self._make_search_string("id:department*")
            self.searcher.delete(q=search_string)
            self.stdout.write(self.style.SUCCESS("Departments dropped from index"))

        self.stdout.write("Indexing departments")

        sql = """
        WITH dept_stats AS (
            SELECT
                e.id as employer_id,
                CASE
                    WHEN parent.name ilike '%%' || e.name || '%%'
                    THEN e.name
                    ELSE parent.name || ' ' || e.name
                END as name,
                e.slug,
                parent.slug as parent_slug,
                eu.name as universe,
                sf.reporting_year,
                COUNT(s.id) as headcount,
                SUM(COALESCE(s.amount, 0) + COALESCE(s.extra_pay, 0)) as expenditure
            FROM payroll_employer e
            JOIN payroll_employer parent ON e.parent_id = parent.id
            LEFT JOIN payroll_employeruniverse eu ON e.universe_id = eu.id
            LEFT JOIN payroll_position p ON e.id = p.employer_id
            LEFT JOIN payroll_job j ON p.id = j.position_id
            LEFT JOIN payroll_salary s ON j.id = s.job_id
            LEFT JOIN data_import_upload u ON s.vintage_id = u.id
            LEFT JOIN data_import_standardizedfile sf ON u.id = sf.upload_id
            WHERE e.parent_id IS NOT NULL
            AND sf.reporting_year = ANY(%s)
            GROUP BY e.id, e.name, e.slug, parent.slug, parent.name, eu.name, sf.reporting_year
            HAVING COUNT(s.id) > 0
        )
        SELECT
            employer_id,
            name,
            slug,
            parent_slug,
            universe,
            reporting_year,
            expenditure,
            headcount
        FROM dept_stats
        ORDER BY employer_id, reporting_year
        """

        documents = []
        document_count = 0

        with connection.cursor() as cursor:
            cursor.execute(sql, [self.reporting_years])

            for row in cursor:
                (
                    employer_id,
                    name,
                    slug,
                    parent_slug,
                    universe,
                    year,
                    expenditure,
                    headcount,
                ) = row

                if headcount and expenditure:
                    display_name = str(name)

                    document = {
                        "id": "department.{}.{}".format(employer_id, year),
                        "slug": slug,
                        "name": display_name,
                        "entity_type": "Employer",
                        "year": year,
                        "expenditure_d": float(expenditure),
                        "headcount_i": headcount,
                        "parent_s": parent_slug,
                        "text": display_name,
                    }

                    if universe:
                        document["universe_s"] = universe

                    documents.append(document)

                    if len(documents) >= self.chunksize:
                        self.searcher.add(documents)
                        document_count += len(documents)
                        documents = []
                        self.stdout.write(
                            "Indexed {} department documents...".format(document_count)
                        )

        if documents:
            self.searcher.add(documents)
            document_count += len(documents)

        self.stdout.write(
            self.style.SUCCESS(
                "Added {} department documents to the index".format(document_count)
            )
        )

    def index_people(self):
        if self.recreate:
            message = "Dropping people from {} from index".format(
                ", ".join(str(year) for year in self.reporting_years)
            )
            self.stdout.write(message)
            search_string = self._make_search_string("id:person*")
            self.searcher.delete(q=search_string)
            self.stdout.write(self.style.SUCCESS("People dropped from index"))

        self.stdout.write("Indexing people")

        sql = """
        WITH person_data AS (
            SELECT DISTINCT ON (p.id, sf.reporting_year)
                p.id as person_id,
                p.slug,
                p.first_name,
                p.last_name,
                sf.reporting_year,
                pos.title,
                e.slug as employer_slug,
                parent.slug as parent_slug,
                e.name as employer_name,
                COALESCE(s.amount, 0) + COALESCE(s.extra_pay, 0) as total_salary
            FROM payroll_person p
            JOIN payroll_job j ON p.id = j.person_id
            JOIN payroll_salary s ON j.id = s.job_id
            JOIN payroll_position pos ON j.position_id = pos.id
            JOIN payroll_employer e ON pos.employer_id = e.id
            LEFT JOIN payroll_employer parent ON e.parent_id = parent.id
            JOIN data_import_upload u ON s.vintage_id = u.id
            JOIN data_import_standardizedfile sf ON u.id = sf.upload_id
            WHERE sf.reporting_year = ANY(%s)
            ORDER BY p.id, sf.reporting_year, s.id DESC  -- Get most recent salary if multiple
        )
        SELECT
            person_id,
            slug,
            first_name,
            last_name,
            reporting_year,
            title,
            employer_slug,
            parent_slug,
            employer_name,
            total_salary
        FROM person_data
        ORDER BY person_id, reporting_year
        """

        documents = []
        document_count = 0

        with connection.cursor() as cursor:
            cursor.execute(sql, [self.reporting_years])

            for row in cursor:
                (
                    person_id,
                    slug,
                    first_name,
                    last_name,
                    year,
                    title,
                    employer_slug,
                    parent_slug,
                    employer_name,
                    total_salary,
                ) = row

                name = "{} {}".format(first_name or "", last_name or "").strip()
                text = "{} {} {}".format(name, employer_name, title or "")

                # Build employer slug list
                employer_slugs = (
                    [parent_slug, employer_slug] if parent_slug else [employer_slug]
                )
                employer_slugs = [s for s in employer_slugs if s]  # Remove None values

                document = {
                    "id": "person.{}.{}".format(person_id, year),
                    "slug": slug,
                    "name": name,
                    "entity_type": "Person",
                    "year": year,
                    "title_s": title or "",
                    "salary_d": float(total_salary),
                    "employer_ss": employer_slugs,
                    "text": text,
                }

                documents.append(document)

                if len(documents) >= self.chunksize:
                    self.searcher.add(documents)
                    document_count += len(documents)
                    documents = []
                    self.stdout.write(
                        "Indexed {} person documents...".format(document_count)
                    )

        if documents:
            self.searcher.add(documents)
            document_count += len(documents)

        self.stdout.write(
            self.style.SUCCESS(
                "Added {} person documents to the index".format(document_count)
            )
        )

    def reindex_one(self, entity_type, entity_id):
        """Keep the existing reindex_one method for individual updates"""
        entity_model_map = {
            "employer": Employer,
            "person": Person,
        }

        update_object = entity_model_map[entity_type].objects.get(id=entity_id)
        id_kwargs = {"id": entity_id}

        if isinstance(update_object, Employer):
            if update_object.is_department:
                index_func = self.index_department
                id_kwargs["type"] = "department"
            else:
                index_func = self.index_unit
                id_kwargs["type"] = "unit"
        elif isinstance(update_object, Person):
            index_func = self.index_person
            id_kwargs["type"] = "person"

        index_id = "{type}.{id}*".format(**id_kwargs)

        self.stdout.write("Dropping {} from index".format(update_object))
        self.searcher.delete(q=index_id)
        self.stdout.write(
            self.style.SUCCESS("{} dropped from index".format(update_object))
        )

        documents = []
        for document in index_func(update_object):
            documents.append(document)

        self.searcher.add(documents)
        success_message = "Added {0} documents for {1} to the index".format(
            len(documents), update_object
        )
        self.stdout.write(self.style.SUCCESS(success_message))

    def index_unit(self, unit):
        name = unit.name
        taxonomy = str(unit.taxonomy) if unit.taxonomy else ""

        of_unit = Q(job__position__employer=unit) | Q(
            job__position__employer__parent=unit
        )

        for year in self.reporting_years:
            in_year = Q(vintage__standardized_file__reporting_year=year)
            salaries = Salary.objects.filter(of_unit & in_year)
            headcount = salaries.count()

            if headcount:
                expenditure = salaries.aggregate(
                    expenditure=Sum(Coalesce("amount", 0)) + Sum(Coalesce("extra_pay", 0))
                )["expenditure"]

                document = {
                    "id": "unit.{0}.{1}".format(unit.id, year),
                    "slug": unit.slug,
                    "name": name,
                    "entity_type": "Employer",
                    "year": year,
                    "taxonomy_s": taxonomy,
                    "size_class_s": unit.size_class or "",
                    "expenditure_d": expenditure,
                    "headcount_i": headcount,
                    "text": name,
                }
                yield document

    def index_department(self, department):
        name = str(department)
        of_department = Q(job__position__employer=department)

        for year in self.reporting_years:
            in_year = Q(vintage__standardized_file__reporting_year=year)
            salaries = Salary.objects.filter(of_department & in_year)
            headcount = salaries.count()

            if headcount:
                expenditure = salaries.aggregate(
                    expenditure=Sum(Coalesce("amount", 0)) + Sum(Coalesce("extra_pay", 0))
                )["expenditure"]

                document = {
                    "id": "department.{0}.{1}".format(department.id, year),
                    "slug": department.slug,
                    "name": name,
                    "entity_type": "Employer",
                    "year": year,
                    "expenditure_d": expenditure,
                    "headcount_i": headcount,
                    "parent_s": department.parent.slug,
                    "text": name,
                }

                if department.universe:
                    document["universe_s"] = str(department.universe)

                yield document

    def index_person(self, person):
        name = str(person)

        for year in self.reporting_years:
            try:
                salary = (
                    Salary.objects.filter(
                        vintage__standardized_file__reporting_year=year,
                        job__person=person,
                    )
                    .select_related(
                        "job__position",
                        "job__position__employer",
                        "job__position__employer__parent",
                    )
                    .get()
                )

                job = salary.job
            except Salary.DoesNotExist:
                continue

            position = job.position
            employer = position.employer
            text = "{0} {1} {2}".format(name, employer, position)

            if employer.is_department:
                employer_slug = [employer.parent.slug, employer.slug]
            else:
                employer_slug = [employer.slug]

            document = {
                "id": "person.{0}.{1}".format(person.id, year),
                "slug": person.slug,
                "name": name,
                "entity_type": "Person",
                "year": year,
                "title_s": job.position.title or "",
                "salary_d": (salary.amount or 0) + (salary.extra_pay or 0),
                "employer_ss": employer_slug,
                "text": text,
            }

            yield document
