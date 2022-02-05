# BLAB Controller

This is the core component of BLAB (BLue Amazon Brain). It is a web server that receives user requests, executes the
appropriate actions using several BLAB components and returns the results.

## Installation:

- Install
  [Python 3.10](https://www.python.org/downloads/release/python-3100/)
  or newer. Also, install `python3-venv` or the equivalent package for the Linux distribution you are using.

- Install [Poetry](https://python-poetry.org/):

```shell
curl -sSL https://install.python-poetry.org | python3 - --preview
```

- In the root directory of the project (that contains this _README.ME_ file)
  run Poetry to install the dependencies:

```shell
poetry install
```

- **(Optional - not necessary in production)**
  To install additional dependencies for development, documentation generation and testing, add the arguments
  `--with dev,doc,test` to the command in the last step.

- Install and set up the database server ([PostgreSQL](https://www.postgresql.org/),
  [MariaDB](https://mariadb.org/), [MySQL](https://www.mysql.com/) or [Oracle](https://www.oracle.com/database/);
  [SQLite](https://www.sqlite.org/index.html) is also supported in development environments). If needed, check
  the [Django documentation on database installation](https://docs.djangoproject.com/en/4.0/ref/databases/).

- Create a database to be used by BLAB (e.g. `CREATE DATABASE blab;`) and a database user that can modify it.

- Install the additional Python dependencies that are specific for the database server:

```shell
# Run only the line that corresponds to the database server that will be used.
poetry install --with=MySQL
poetry install --with=Oracle
poetry install --with=PostgreSQL
poetry install --with=SQLite3
```

- In *blab-controller/controller/settings/*, create a copy of the file *prod_TEMPLATE.py* and name it *prod.py*. Fill in
  the fields following the instructions on the file and the linked documentation.

- Set the environment variable `DJANGO_SETTINGS_MODULE` to _controller.settings.dev_ or _controller.settings.prod_ (for
  development and production environments, respectively). This can be done using system tools, cloud server
  settings [or a secret *blab-controller/controller/.env* file](https://github.com/theskumar/python-dotenv).

- Let Django create the database tables:
```shell
poetry run ./blab-controller/manage.py migrate
```
