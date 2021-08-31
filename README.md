# 💰 bga-payroll

How much do your public officials make?

## Running the app locally

### Requirements

- 🐳 [Docker](https://hub.docker.com/search/?type=edition&offering=community)

### Getting started

Perform the following steps from your terminal.

Clone this repository and `cd` into your local copy.

```bash
git clone https://github.com/datamade/bga-payroll.git
cd bga-payroll
```

Next, copy `bga_database/local_settings.py.example` from `bga_database/local-settings.py`.

```bash
cp bga_database/local-settings.example.py bga_database/local-settings.py
```

Finally, build and run the applicaton.

```bash
docker-compose up -d --build
```

Once the command exits, you can visit the app in your browser at
http://localhost:8000.

To view logs for `app`, `worker`, or any of the other services defined in
`docker-compose.yml`, run `docker-compose logs -f <SERVICE_NAME>`, e.g.,
`docker-compose logs -f app`.

### Adding data

The application will work without data, but if you'd like to add some,
you have two options: Restore from a database dump, or create and upload a data file.

#### Restore from a database dump

DataMaders can make or request a dump of the staging database in the #bga-payroll Slack channel.

To create a dump, you must have SSH access to the staging server. Provided that's true, run the following command in your terminal, swapping in the correct value for `${STAGING_URL}`:

```bash
ssh ubuntu@${STAGING_URL} pg_dump -U postgres -Fc -O -d bga_payroll > bga_payroll.dump
```

When restoring a database, it's important that your local database is empty. So, remove your data volumes prior to restoring.

```bash
docker-compose down --volumes
```

Then, bring your database service up. This will create the `bga_payroll` database.

```bash
docker-compose up postgres
```

When your database is ready, you'll see output like this:

```bash
bga-payroll-postgres | PostgreSQL init process complete; ready for start up.
bga-payroll-postgres |
bga-payroll-postgres | 2021-08-18 16:31:36.869 UTC [1] LOG:  listening on IPv4 address "0.0.0.0", port 5432
bga-payroll-postgres | 2021-08-18 16:31:36.869 UTC [1] LOG:  listening on IPv6 address "::", port 5432
bga-payroll-postgres | 2021-08-18 16:31:36.873 UTC [1] LOG:  listening on Unix socket "/var/run/postgresql/.s.PGSQL.5432"
bga-payroll-postgres | 2021-08-18 16:31:36.890 UTC [75] LOG:  database system was shut down at 2021-08-18 16:31:36 UTC
bga-payroll-postgres | 2021-08-18 16:31:36.895 UTC [1] LOG:  database system is ready to accept connections
```

In a separate terminal window, run `pg_restore` to load your dump into your containerized database.

```
docker exec -i bga-payroll-postgres pg_restore -U postgres -Fc -O -v -d bga_payroll < bga_payroll.dump
```

Finally, start the app:

```bash
docker-compose up
```

N.b., if you need search for development, you also need to build the search index. This command will add employers from 2018 to the index. Add people to the entity types argument, if you need to.

```bash
docker-compose exec app python manage.py build_solr_index --reporting_year 2018 --entity-types units,departments --chunksize=25
```

#### Create and upload a data file

First, make a formatted data file.

```bash
docker-compose exec app make payroll-actual-2017-pt-1.csv
```

This will process `data/raw/payroll-actual-2017-pt-1.csv` into a file called `payroll-actual-2017-pt-1.csv`.

Next, create a superuser, so you can log into the data import interface.

```bash
docker-compose exec app python manage.py createsuperuser
```

Finally, go to http://localhost:8000/data-import/ and follow the steps to upload the CSV you just made. Don't forget to put in the data year!

It will take a bit to complete each step of the data import. You can refresh the page to see if it's ready to move on to the next section. (The status will have changed.) You can also keep track of progress in your worker terminal by running:

```bash
docker-compose logs -f worker
```
