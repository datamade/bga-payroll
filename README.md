# 💰 bga-payroll

How much do your public officials make?

## Requirements

- Python 3.x
- Postgres >= 9
- GNU Make
- Solr 7.x

## Running the app locally

Perform the following steps from your terminal.

1. Clone this repository and `cd` into your local copy.

    ```bash
    git clone https://github.com/datamade/bga-payroll.git
    cd bga-payroll
    ```
2. Create a virtual environment. (We recommend using [`virtualenvwrapper`](http://virtualenvwrapper.readthedocs.org/en/latest/install.html) for working in a virtualized development environment.)

    ```bash
    mkvirtualenv bga
    ```
3. Install the requirements.

    ```bash
    pip install -r requirements.txt
    ```
4. Copy the local settings file. Note that you may need to update `DATABASES` in your own copy of `local_settings.py` to reflect your local Postgres setup.

    ```bash
    cp bga_database/local_settings.py.example bga_database/local_settings.py
    ```
5. Create the database and run the migrations.

    ```bash
    make database
    python manage.py migrate
    ```
6. Run the app. In four seperate terminal windows:

    ```bash
    redis-server
    ```

    ```bash
    celery --app=bga_database.celery:app worker --loglevel=DEBUG
    ```
    
    ```bash
    solr start && solr create -c bga -d ./solr_configs
    ```

    ```bash
    python manage.py runserver
    ```
7. In the project directory, make a test data file.
    ```bash
    make 2016-formatted.csv
    ```

8. Go to `http://localhost:8000/data-import/` and follow the steps to upload the CSV you just made. Don't forget to put in the data year. It will take a bit to complete each step, you can refresh the page to see if it's ready to move on to the next section. You can also keep track of progress in your Celery terminal.
