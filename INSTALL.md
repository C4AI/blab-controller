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
  `--with dev,doc,test` to the command in the last step. To avoid the installation of
  production-only dependencies, add `--without prod`.

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
    Example - Apache
    </summary>

    - Install [mod_wsgi](https://modwsgi.readthedocs.io/en/develop/index.html). It is available as the `libapache2-mod-wsgi-py3` package in
      Debian-based Linux distributions, but it is usually outdated and it has to be built using the same Python version that will be used. Alternatively, run `poetry run pip install mod_wsgi` to compile it and install it on demand, then run `mod_wsgi-express module-config` and copy the first output line (*LoadModule wsgi_module...*) to the beginning of the file described in the next item.

    - If running on a Debian-based Linux distribution, create the file
      */etc/apache2/sites-available/blab-controller.conf* with the following contents:
  ```ApacheConf
  Define BLAB_CONTROLLER_ROOT /full/path/to/blab-controller

  WSGIScriptAlias /api ${BLAB_CONTROLLER_ROOT}/blab-controller/controller/wsgi.py
  WSGIPythonHome ${BLAB_CONTROLLER_ROOT}/.venv
  WSGIPythonPath ${BLAB_CONTROLLER_ROOT}

  <Directory ${BLAB_CONTROLLER_ROOT}/blab-controller/controller>
      <Files wsgi.py>
          Require all granted
      </Files>
  </Directory>
  ```
  Then, run `a2ensite blab-controller` to enable the site configuration. In other distributions, the contents
  can be added to an existing file such as `/etc/apache/httpd.conf`.

    - Restart Apache (`systemctl reload apache2`).
  </details>
