# BLAB Controller - Installation instructions

- Install
  [Python 3.10](https://www.python.org/downloads/release/python-3100/)
  or newer. Also, install `python3-venv` or the equivalent package for the Linux distribution you are using.

- Install [Poetry](https://python-poetry.org/):

```shell
curl -sSL https://install.python-poetry.org | python3 - --preview
```

- In the root directory of the project (that contains this _README.ME_ file)
  run Poetry to install the dependencies in a new virtual environment (_.venv_):

```shell
POETRY_VIRTUALENVS_IN_PROJECT=true poetry install
```

- **(In development and test environments)** <br/>
  To install additional dependencies for development, documentation generation and testing, add the arguments
  `--with dev,doc,test` to the command in the last step. To avoid the installation of production-only dependencies,
  add `--without prod`.

- Install and set up the database server ([PostgreSQL](https://www.postgresql.org/),
  [MariaDB](https://mariadb.org/), [MySQL](https://www.mysql.com/) or [Oracle](https://www.oracle.com/database/)). If
  needed, check
  the [Django documentation on database installation](https://docs.djangoproject.com/en/4.0/ref/databases/). In
  development environments, [SQLite](https://www.sqlite.org/index.html) is also supported.

- **(In production environment)** <br/>
  Create a database to be used by BLAB (e.g. `CREATE DATABASE blab;`) and a database user that can modify it.

- Install the additional Python dependencies that are specific for the database server:

```shell
# Run only the line that corresponds to the database server that will be used.
poetry install --with=MySQL
poetry install --with=Oracle
poetry install --with=PostgreSQL
poetry install --with=SQLite3
```

- Set the environment variable `DJANGO_SETTINGS_MODULE` to _controller.settings.dev_ or _controller.settings.prod_ (for
  development and production environments, respectively). This can be done using system tools, cloud server
  settings [or a secret *blab-controller/controller/.env* file](https://github.com/theskumar/python-dotenv).

- **(In production environment)** <br/>
  In *blab-controller/controller/settings/*, create a copy of the file *prod_TEMPLATE.py* and name it *prod.py*. Fill in
  the fields following the instructions on the file and the linked documentation.

- Let Django create the database tables:

```shell
poetry run ./blab-controller/manage.py migrate
```

- **(In development environment)** <br/>
  To start the development server, run:

```shell
poetry run ./blab-controller/manage.py runserver
```

- **(In production environment)** <br/>
  Follow [Django's instructions](https://docs.djangoproject.com/en/4.0/howto/deployment/) to set up the interaction
  between the web server and the controller written in Python.
  <details>
    <summary>
    Example - using Apache, Gunicorn and Daphne on a Debian-based Linux distribution
    </summary>

    - Enable [*mod_proxy_http*](https://httpd.apache.org/docs/2.4/mod/mod_proxy_http.html) and
      [*mod_rewrite*](https://httpd.apache.org/docs/2.4/mod/mod_rewrite.html) modules by
      running `a2enmod proxy_http rewrite` as root.
    - Create the file
      */etc/apache2/sites-available/blab-controller.conf* with the following contents:
  ```ApacheConf
  Define BLAB_CONTROLLER_ROOT /full/path/to/blab-controller

  ProxyPass /static/ !
  ProxyPass /media/ !
  ProxyPass /api/ http://localhost:8000/api/
  ```
    - Run `a2ensite blab-controller` as root to enable the site configuration.

    - Create the file */etc/systemd/system/blab-gunicorn.service* with the following contents, changing the username and
      paths as needed:
  ```ini
  [Unit]
  Description=Gunicorn daemon
  After=network.target

  [Service]
  User=user_name_here
  Group=www-data
  Restart=always
  WorkingDirectory=/full/path/to/blab-controller/blab-controller
  ExecStart=/full/path/to/blab-controller/.venv/bin/python -m gunicorn controller.wsgi

  [Install]
  WantedBy=multi-user.target
  ```
    - Run `systemctl enable blab-gunicorn` and `systemctl start blab-gunicorn` to enable the service and start it
      immediately.
    - Restart Apache (`systemctl reload apache2` as root).
  </details>
