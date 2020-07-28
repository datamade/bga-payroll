# A brief overview of `bga-payroll` architecture

There are two Django applications in the BGA Public Salaries Database project:
The public user interface (`payroll`), and the private interface for uploading
data (`data_import`).

- [Payroll](#the-payroll-application)
  - [Models](#models)
  - [Views](#views)
  - [Search](#search)
  - [Caching](#caching)
- [Data import](#the-data_import-application)
  - [Standardized file upload](#standardized-file-upload)
  - [Source file upload](#source-file-upload)
- [Tests](#tests)

## The `payroll` application

### Models

`payroll` is a fairly straightforward application. It contains [the core
models](https://github.com/datamade/bga-payroll/tree/master/payroll/models.py) – Employer,
Position, Person, Job, and Salary. The models are so normalized because an
employer has many positions, more than one person can hold the same position,
and a person in the same position can have many different salaries over the
years.

### Views

The `payroll` app defines the homepage and detail views for Employer [proxy
models](https://docs.djangoproject.com/en/3.0/topics/db/models/#proxy-models)
Unit and Department, as well as the Person model. (Proxying Employer into Unit
and Department means that we have a cleaner way to differentiate Python logic
between the two types of Employer, while still leveraging the same underlying
database table.)

**🚨 Note that this project uses [the `jinja2` templating
engine](https://jinja.palletsprojects.com/en/2.11.x/) for application views. 🚨**

The `payroll` templates also make use of a modified version of [the DataMade
`django-compressor` stack](https://github.com/datamade/how-to/blob/master/django/django-compressor.md)
to translate contemporary ES6 JavaScript into more widely compatible ES5 syntax.

In order to reduce load time on first visit, the `payroll` app separates template
loading from most database queries. Instead, it performs the database queries
asynchronously via AJAX calls to an API implemented with [the Django REST
Framework](https://www.django-rest-framework.org/).

Finally, the `payroll` application also exposes Django admin views to edit
employer name and classification.

### Search

Search is a bit more complicated. `payroll` uses [the Solr search
engine](https://lucene.apache.org/solr/) with custom Python adapters to
[index](https://github.com/datamade/bga-payroll/tree/master/payroll/management/commands/build_solr_index.py)
and [search](https://github.com/datamade/bga-payroll/tree/master/payroll/search.py) Employer
and Person payroll records.

### Caching

We use Django's database cache backend to cache `payroll` views. More
specifically:

- Translating ES6 to ES5 is a relatively heavy operation, so the index and entity
pages, including their compiled JavaScript, are cached in their entirety.
- Database operations to gather display data for a given year are also fairly
intensive, so API views are cached as well.

## The `data_import` application

The `data_import` application has more moving parts: If defines models to
contain and operate on uploaded data - namely Upload, RespondingAgency,
StandardizedFile, and SourceFile - as well as the views to perform those
operations.

### Standardized file upload

A StandardizedFile is a data file following a standard data format for import
into the database.

`data_import` defines a user interface to upload and interactively import data
from standardized data files. The interactive import has a number of moving
parts:

- The import itself is a "finite state machine" governed by
  [`django-fsm`](https://github.com/viewflow/django-fsm). In other words, for
  each standardized file, there is a series of steps and instructions for moving
  from Step A to Step B and so on. The steps ("states") and their transitions
  are defined on the StandardizedFile model.
- Each transition in the state machine refers to a series of
  [tasks](https://github.com/datamade/bga-payroll/tree/master/data_import/tasks.py). These
  tasks can take a long time, so we use
  [`celery`](http://www.celeryproject.org/) to queue and run tasks
  asynchronously, i.e., in the background.
- Each delayed task leverages an instance of ImportUtility. [This class mostly
  defines methods to run SQL
  queries](https://github.com/datamade/bga-payroll/tree/master/data_import/utils/import_utility.py)
  that transform the flat, standardized data into instances of the `payroll`
  models.
- The import is interactive because there are several occasions during the
  import process where we ask the user to review entities in the incoming data,
  e.g., when it contains a responding agency or employer that we haven't seen
  before. We use [Redis](https://redis.io/), an in-memory data store, and a
  Python library called
  [`saferedisqueue`](https://pypi.org/project/saferedisqueue/) to queue records
  for review. Custom queue logic is defined in
  [`queues.py`](https://github.com/datamade/bga-payroll/tree/master/data_import/utils/queues.py),
  the queues are populated by methods on the ImportUtility class, and the review
  routes are defined in
  [`views.py`](https://github.com/datamade/bga-payroll/tree/master/data_import/queues.py).

### Source file upload

A SourceFile is a raw response file from an agency FOIA'ed by the BGA.
`data_import` [exposes an
interface](https://github.com/datamade/bga-payroll/tree/master/data_import/admin.py) for
uploading source files via the Django admin interface.

Standardized files and source files are tied together by (1) RespondingAgency
and (2) data year. The core `payroll` models all have a `source_file` method
that leverage this relationship to retrieve the source file for a given year.

## Tests

Both the `payroll` and `data_import` applications have tests. These can be found
in [the `tests/` directory](https://github.com/datamade/bga-payroll/tree/master/tests/) 
at the root of the project. In general, these tests follow the guidance set out in 
[the DataMade testing guidelines](https://github.com/datamade/testing-guidelines).
`data_import/test_tasks.py`, in particular, organizes tests into `TestX` classes to
minimize redundant code.
