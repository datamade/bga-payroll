# 💰 bga-payroll

How much do your public officials make?

## Running the app locally

### Requirements

- 🐳 [Docker](https://hub.docker.com/search/?type=edition&offering=community)

### Getting started

Perform the following steps from your terminal.

1. Clone this repository and `cd` into your local copy.

    ```bash
    git clone https://github.com/datamade/bga-payroll.git
    cd bga-payroll
    ```
2. Build and run the applicaton.

    ```bash
    docker-compose up -d --build
    ```

    Once the command exits, you can visit the app in your browser at
    http://localhost:8000.

    To view logs for `app`, `worker`, or any of the other services defined in
    `docker-compose.yml`, run `docker-compose logs -f <SERVICE_NAME>`, e.g.,
    `docker-compose logs -f app`.

3. The application will work without data, but if you'd like to add some,
first make a formatted data file.

    ```bash
    docker-compose exec app make payroll-actual-2017-pt-1.csv
    ```

    This will process `data/raw/payroll-actual-2017-pt-1.csv` into a file called `payroll-actual-2017-pt-1.csv`.

4. Next, create a superuser, so you can log into the data import interface.

    ```bash
    docker-compose exec app python manage.py createsuperuser
    ```

5. Finally, go to http://localhost:8000/data-import/ and follow the steps to upload the CSV you just made. Don't forget to put in the data year!

    It will take a bit to complete each step of the data import. You can refresh the page to see if it's ready to move on to the next section. (The status will have changed.) You can also keep track of progress in your worker terminal by running:

    ```bash
    docker-compose logs -f worker
    ```
