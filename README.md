# 💰 bga-payroll

How much do your public officials make?

## Requirements

- Python 3.x
- Postgres
- GNU Make

## Running the app locally

Perform the following steps from your terminal.

1. Clone this repository and `cd` into your local copy.

    ```bash
    git clone https://github.com/datamade/bga-payroll.git
    cd bga-payroll
    ```
2. Create a virtual environment. (We recommend using [`virtualenv`](http://virtualenv.readthedocs.org/en/latest/virtualenv.html) and [`virtualenvwrapper`](http://virtualenvwrapper.readthedocs.org/en/latest/install.html) for working in a virtualized development environment.)

    ```bash
    mkvirtualenv bga
    ```
3. Install the requirements.

    ```bash
    pip install -r requirements.txt
    ```
4. Create the database and add 2017 data. (This may take a couple of minutes.)

    ```bash
    make database
    ```
5. Run the app.

    ```bash
    python manage.py runserver
    ```
