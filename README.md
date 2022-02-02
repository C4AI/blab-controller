# BLAB Controller

This is the core component of BLAB (BLue Amazon Brain).
It is a web server that receives user requests,
executes the appropriate actions using several BLAB components
and returns the results.

## Installation:

- Install
  [Python 3.10](https://www.python.org/downloads/release/python-3100/)
  or newer.

- Install [Poetry](https://python-poetry.org/):

```shell
curl -sSL https://install.python-poetry.org | python3 - --preview
```

- Install the dependencies using Poetry:

```shell
poetry install
```

- **(Optional - not necessary in production)**
  To install additional dependencies for development, documentation generation and testing, add the arguments
  `--with dev,doc,test` to the command in the last step.

- In *blab-controller/controller/settings/*, create a copy of the file *prod_TEMPLATE.py* named *prod.py*.
  Fill in the fields following the instructions on the file and the linked documentation.
